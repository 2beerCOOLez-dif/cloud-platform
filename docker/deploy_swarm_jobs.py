r"""Deploy five distinct tasks: db, migrate, collectstatic, web and nginx.

Run from Windows CMD: python docker\deploy_swarm_jobs.py --copy-from-compose
Only the Python standard library and the installed Docker CLI are required.
"""
import argparse
import datetime
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANAGER = "cloud-swarm-manager"
WORKER = "cloud-swarm-worker"
STACK = "cloud_platform"
REMOTE = "/opt/cloud-platform-jobs"
EXPECTED = {f"{STACK}_db": "1/1", f"{STACK}_nginx": "1/1", f"{STACK}_web": "1/1"}


class DeploymentError(Exception):
    pass


def safe_diagnostic(text):
    """Hide known secret values while preserving useful Docker diagnostics."""
    try:
        lines = (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        lines = []
    for line in lines:
        name, separator, value = line.partition("=")
        if separator and any(word in name.upper() for word in ("PASSWORD", "SECRET", "TOKEN")):
            value = value.strip().strip("\"'")
            if value:
                text = text.replace(value, "[hidden]")
    return text


def docker(*arguments, capture=False, timeout=900):
    command = ["docker", *map(str, arguments)]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if result.returncode:
        details = (result.stderr or result.stdout or "No diagnostic output.").strip()
        message = (f"Docker command failed (exit {result.returncode}).\n"
                   f"Command: {subprocess.list2cmdline(command)}\n{details}")
        raise DeploymentError(safe_diagnostic(message))
    if not capture and result.stderr:
        print(safe_diagnostic(result.stderr), file=sys.stderr, end="", flush=True)
    return (result.stdout or "").strip()


def manager(*arguments, capture=False, timeout=900):
    return docker("exec", MANAGER, "docker", *arguments, capture=capture, timeout=timeout)


def wait_until(function, description, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = function()
            if result:
                return result
        except (DeploymentError, OSError, ValueError):
            pass
        time.sleep(3)
    raise DeploymentError(f"Timeout: {description}")


def check_cluster():
    names = docker("ps", "--format", "{{.Names}}", capture=True).splitlines()
    if MANAGER not in names or WORKER not in names:
        raise DeploymentError("Start compose.cluster.yaml: both cluster nodes must be running.")
    rows = manager("node", "ls", "--format", "{{.Hostname}}|{{.Status}}|{{.Availability}}|{{.ManagerStatus}}", capture=True)
    nodes = {parts[0]: parts[1:] for parts in (row.split("|") for row in rows.splitlines())}
    for name in ("swarm-manager", "swarm-worker"):
        if nodes.get(name, [])[:2] != ["Ready", "Active"]:
            raise DeploymentError(f"Node {name} must be Ready and Active.")
    if nodes["swarm-manager"][2] != "Leader":
        raise DeploymentError("swarm-manager must be the leader.")


def copy_configuration():
    files = {
        ".env": ".env",
        "stack.jobs.yaml": "stack.jobs.yaml",
        "nginx/swarm-jobs.conf": "nginx/swarm-jobs.conf",
    }
    for local in files:
        if not (ROOT / local).is_file():
            raise DeploymentError(f"Missing project file: {local}")
    docker("exec", MANAGER, "mkdir", "-p", f"{REMOTE}/nginx")
    for local, remote in files.items():
        docker("cp", local, f"{MANAGER}:{REMOTE}/{remote}", capture=True)
    docker("exec", MANAGER, "chmod", "600", f"{REMOTE}/.env")


def deploy_with_web_stopped():
    # env_file loads application settings. WEB_REPLICAS is an explicit CLI variable.
    docker("exec", "-e", "WEB_REPLICAS=0", "-e", "NGINX_REPLICAS=0", MANAGER, "docker", "stack", "deploy",
           "--resolve-image", "always", "--compose-file", f"{REMOTE}/stack.jobs.yaml", STACK)
    def stopped():
        for name in ("web", "nginx"):
            states = manager("service", "ps", f"{STACK}_{name}", "--format", "{{.CurrentState}}", capture=True)
            if any(state.startswith("Running") for state in states.splitlines()):
                return False
        return True

    wait_until(stopped, "web and nginx to stop before preparation")


def ready_database():
    ids = manager("ps", "--filter", f"label=com.docker.swarm.service.name={STACK}_db", "--format", "{{.ID}}", capture=True).splitlines()
    for container_id in ids:
        status = manager("inspect", "--format", "{{.State.Health.Status}}", container_id, capture=True)
        if status == "healthy":
            return container_id
    return None


def database_names(command, container_id):
    values = command("exec", container_id, "printenv", "POSTGRES_USER", "POSTGRES_DB", capture=True).splitlines()
    if len(values) != 2 or not all(values):
        raise DeploymentError("POSTGRES_USER and POSTGRES_DB must be set in the database container.")
    return values


def copy_compose_database(database_id):
    target_user, target_database = database_names(manager, database_id)
    count = manager("exec", database_id, "psql", "-U", target_user, "-d", target_database, "-Atc",
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';",
                    capture=True)
    if int(count) != 0:
        print("Swarm database already contains tables. Existing data will be kept.", flush=True)
        return

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"swarm_transfer_{stamp}.dump"
    backup = ROOT / "backups" / filename
    backup.parent.mkdir(parents=True, exist_ok=True)
    compose = ("compose", "-f", "compose.yaml", "-f", "compose.deploy.yaml")
    source_ids = docker(*compose, "ps", "-q", "db", capture=True).splitlines()
    if len(source_ids) != 1:
        raise DeploymentError(
            "The original Compose db container is not running. Start the original platform, "
            "then rerun with --copy-from-compose."
        )
    source_id = source_ids[0]
    source_user, source_database = database_names(docker, source_id)
    print("Creating a backup of the existing Compose database...", flush=True)
    docker("exec", source_id, "pg_dump", "-U", source_user, "-d", source_database,
           "-Fc", "-f", f"/tmp/{filename}")
    relative_backup = backup.relative_to(ROOT).as_posix()
    print("Copying the backup to the project backups folder...", flush=True)
    docker("cp", f"{source_id}:/tmp/{filename}", relative_backup, capture=True)
    if backup.stat().st_size == 0:
        raise DeploymentError("The database backup is empty.")
    print("Transferring the backup to the Swarm manager...", flush=True)
    # DinD mounts /tmp inside its mount namespace. An outer docker cp may write
    # underneath that mount, where docker exec and the inner CLI cannot see it.
    # Configuration files already use this ordinary /opt directory successfully.
    manager_backup = f"{REMOTE}/{filename}"
    docker("cp", relative_backup, f"{MANAGER}:{manager_backup}", capture=True)
    docker("exec", MANAGER, "test", "-s", manager_backup, capture=True)
    manager("cp", manager_backup, f"{database_id}:/tmp/{filename}", capture=True)
    print("Restoring the backup into the empty Swarm database...", flush=True)
    manager("exec", database_id, "pg_restore", "-U", target_user, "-d", target_database,
            "--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction",
            f"/tmp/{filename}")
    print(f"Backup saved: backups/{filename}", flush=True)


def task_status(service):
    ids = manager("service", "ps", service, "-q", "--no-trunc", capture=True).splitlines()
    if not ids:
        return None
    # Jobs created by this script have one task, with retries disabled.
    return json.loads(manager("inspect", "--type", "task", "--format", "{{json .Status}}", ids[0], capture=True))


def completed_successfully(status):
    return bool(status and status.get("State") == "complete"
                and status.get("ContainerStatus", {}).get("ExitCode") == 0)


def existing_jobs():
    services = set(manager("service", "ls", "--format", "{{.Name}}", capture=True).splitlines())
    existing = []
    for role in ("migrate", "collectstatic"):
        service = f"{STACK}_{role}"
        if service not in services:
            continue
        mode = json.loads(manager("service", "inspect", service, "--format", "{{json .Spec.Mode}}", capture=True))
        if "ReplicatedJob" not in mode:
            raise DeploymentError(f"{service} exists but is not a replicated job; it was not removed.")
        status = task_status(service)
        if status is None or status.get("State") not in {"complete", "failed", "rejected", "shutdown", "orphaned"}:
            raise DeploymentError(f"{service} is still active. Wait for its completion before redeploying.")
        existing.append(service)
    return existing


def create_job(role, image):
    if role not in {"migrate", "collectstatic"}:
        raise DeploymentError(f"Unknown job: {role}")
    arguments = [
        "service", "create", "--detach", "--name", f"{STACK}_{role}",
        "--mode", "replicated-job", "--replicas", "1",
        "--restart-condition", "none", "--no-healthcheck",
        "--constraint", "node.hostname==swarm-manager",
        "--label", f"com.docker.stack.namespace={STACK}",
        "--container-label", f"com.docker.stack.namespace={STACK}",
        "--env-file", f"{REMOTE}/.env",
        "--env", f"DB_HOST={STACK}_db", "--env", "DB_PORT=5432",
        "--env", "DJANGO_DEBUG=False",
        "--network", f"{STACK}_backend",
        "--workdir", "/app", "--entrypoint", "python",
    ]
    if role == "collectstatic":
        arguments.extend([
            "--user", "0", "--mount",
            f"type=volume,source={STACK}_static_data,target=/app/staticfiles",
        ])
    arguments.extend([image, "manage.py", role, "--noinput"])
    manager(*arguments)


def wait_for_job(role, timeout=600):
    service = f"{STACK}_{role}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = task_status(service)
        if completed_successfully(status):
            print(f"{role}: Completed, exit code 0", flush=True)
            return
        if status and status.get("State") in {"complete", "failed", "rejected", "shutdown", "orphaned"}:
            manager("service", "logs", "--tail", "40", service)
            raise DeploymentError(f"Job {role} failed; web and nginx will not be started.")
        time.sleep(3)
    raise DeploymentError(f"Timeout waiting for {role}. Inspect its service logs.")


def service_counts():
    text = manager("service", "ls", "--filter", f"label=com.docker.stack.namespace={STACK}",
                   "--format", "{{.Name}}|{{.Replicas}}", capture=True)
    actual = dict(line.split("|", 1) for line in text.splitlines())
    names = set(EXPECTED) | {f"{STACK}_migrate", f"{STACK}_collectstatic"}
    return set(actual) == names and all(actual[name] == count for name, count in EXPECTED.items())


def check_jobs():
    for role in ("migrate", "collectstatic"):
        if not completed_successfully(task_status(f"{STACK}_{role}")):
            raise DeploymentError(f"Job {role} is not successfully completed.")


def check_browser_urls():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for path in ("/", "/static/admin/css/base.css"):
        with opener.open(f"http://127.0.0.1:8082{path}", timeout=15) as response:
            if response.status != 200:
                return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copy-from-compose", action="store_true",
                        help="Copy Compose data only into an empty Swarm database.")
    arguments = parser.parse_args()
    print("1/7 Checking the two Swarm nodes...", flush=True)
    check_cluster()
    previous_jobs = existing_jobs()
    print("2/7 Starting PostgreSQL; web and nginx remain stopped...", flush=True)
    copy_configuration()
    deploy_with_web_stopped()
    database_id = wait_until(ready_database, "PostgreSQL healthcheck", timeout=600)
    if arguments.copy_from_compose:
        copy_compose_database(database_id)
    else:
        print("Swarm uses its own database; Compose data is not copied.", flush=True)
    image = manager("service", "inspect", f"{STACK}_web", "--format",
                    "{{.Spec.TaskTemplate.ContainerSpec.Image}}", capture=True)
    manager("volume", "create", f"{STACK}_static_data", capture=True)
    for service in previous_jobs:
        # Only finished job services are removed, so the two tasks can run again.
        # Their shared database and static volume are preserved.
        manager("service", "rm", service)
    print("3/7 Running the migrate job...", flush=True)
    create_job("migrate", image)
    wait_for_job("migrate")
    print("4/7 Running the collectstatic job...", flush=True)
    create_job("collectstatic", image)
    wait_for_job("collectstatic")
    print("5/7 Starting one web container on swarm-worker...", flush=True)
    manager("service", "scale", "--detach", f"{STACK}_web=1")

    def web_ready():
        states = manager("service", "ps", f"{STACK}_web", "--filter", "desired-state=running",
                         "--format", "{{.Node}}|{{.CurrentState}}", capture=True).splitlines()
        if len(states) != 1 or not states[0].startswith("swarm-worker|Running"):
            return False
        ids = docker("exec", WORKER, "docker", "ps", "--filter",
                     f"label=com.docker.swarm.service.name={STACK}_web", "-q", capture=True).splitlines()
        return len(ids) == 1 and docker("exec", WORKER, "docker", "inspect", "--format",
                                        "{{.State.Health.Status}}", ids[0], capture=True) == "healthy"

    wait_until(web_ready, "healthy web container on swarm-worker", timeout=600)
    print("6/7 Starting nginx and checking the website...", flush=True)
    manager("service", "scale", "--detach", f"{STACK}_nginx=1")
    wait_until(service_counts, "three running services and two job services", timeout=600)
    wait_until(check_browser_urls, "HTTP and static files on localhost:8082", timeout=120)
    print("7/7 Checking both completed jobs...", flush=True)
    check_jobs()
    manager("stack", "services", STACK)
    for role in ("migrate", "collectstatic"):
        manager("service", "ps", f"{STACK}_{role}", "--no-trunc")
    print("Deployment complete: db, web, nginx running; migrate and collectstatic completed.", flush=True)
    print("Open http://localhost:8082/", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (DeploymentError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Deployment stopped: {error}", file=sys.stderr)
        print("Inspect: docker exec cloud-swarm-manager docker stack ps cloud_platform --no-trunc", file=sys.stderr)
        print("Inspect: docker exec cloud-swarm-manager docker service logs --tail 40 cloud_platform_migrate", file=sys.stderr)
        print("Inspect: docker exec cloud-swarm-manager docker service logs --tail 40 cloud_platform_collectstatic", file=sys.stderr)
        sys.exit(1)

