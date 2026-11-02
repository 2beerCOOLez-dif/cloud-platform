import os
import subprocess
import sys


def main():
    subprocess.run(
        [
            sys.executable,
            "manage.py",
            "migrate",
            "--noinput",
        ],
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            "manage.py",
            "collectstatic",
            "--noinput",
        ],
        check=True,
    )

    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()