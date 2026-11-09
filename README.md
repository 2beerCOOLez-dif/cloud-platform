# Платформа управления дистанционными образовательными курсами

Учебное приложение на Django: преподаватели создают курсы, уроки и задания, студенты записываются на обучение, отправляют ответы и просматривают оценки. Администратор управляет пользователями и ролями через панель Django.

[GitHub](https://github.com/2beerCOOLez-dif/cloud-platform) · [Docker Hub](https://hub.docker.com/r/2beercoolez1/cloud-platform) · [GitHub Actions](https://github.com/2beerCOOLez-dif/cloud-platform/actions)

## Возможности и технологии

- Курсы, уроки, текстовые задания и видео YouTube, Rutube и Vimeo.
- Один ответ студента на задание, оценка от 0 до 100 и комментарий преподавателя.
- Проверка прав доступа: преподаватель управляет своими курсами, студент видит доступные ему материалы и свои ответы.
- Пользователей создаёт администратор; публичной регистрации нет.

Технологии: Python 3.12, Django, Gunicorn, PostgreSQL 17, Nginx, Docker Compose и Docker Swarm. GitHub Actions проверяет код, собирает образ и публикует его в Docker Hub. Развёртывание запускает администратор.

## Подготовка

Для Compose нужны Git и Docker с Compose v2. Для сценария Swarm дополнительно нужен Python 3.12; сторонние Python-пакеты для него не требуются. В Windows Docker Desktop должен работать с Linux-контейнерами. Команды ниже выполняются в CMD из корня проекта.

```cmd
git clone https://github.com/2beerCOOLez-dif/cloud-platform.git
cd cloud-platform
copy .env.example .env
```

Если проект и `.env` уже существуют, используйте их. В `.env` задайте свои `POSTGRES_PASSWORD` и `DJANGO_SECRET_KEY`, оставьте `DJANGO_DEBUG=False` и разрешённые хосты `localhost,127.0.0.1`. Файл с секретами не добавляйте в Git.

## Запуск через Docker Compose

```cmd
docker compose -f compose.yaml -f compose.deploy.yaml up -d --no-build --pull always --wait --wait-timeout 180
docker compose -f compose.yaml -f compose.deploy.yaml ps
```

Запускаются три сервиса: `db` — PostgreSQL, `web` — Django через Gunicorn, `nginx` — приём HTTP-запросов и выдача статики. При запуске `web` автоматически выполняются миграции и сбор статических файлов. Ожидаемое состояние всех сервисов — `healthy`.

Сайт: [http://localhost:8081/](http://localhost:8081/). Административная панель: [http://localhost:8081/admin/](http://localhost:8081/admin/).

На новой базе создайте администратора:

```cmd
docker compose -f compose.yaml -f compose.deploy.yaml exec web python manage.py createsuperuser
```

Для локальной сборки изменённого кода используйте `docker compose up -d --build --wait`. Это другой способ запуска того же Compose-проекта, а не отдельная платформа.

## Запуск через Docker Swarm

Используется подготовленный двухузловой кластер Docker-in-Docker: контейнеры `cloud-swarm-manager` и `cloud-swarm-worker`, внутри которых работают узлы `swarm-manager` и `swarm-worker`. Оба узла должны быть `Ready` и `Active`, управляющий — `Leader`.

```cmd
docker exec cloud-swarm-manager docker node ls
python docker\deploy_swarm_jobs.py --copy-from-compose
```

Флаг `--copy-from-compose` переносит пользователей и учебные материалы из работающей Compose-платформы в пустую базу Swarm. Исходная база не изменяется, архив сохраняется в `backups`. Если база Swarm уже содержит таблицы, перенос пропускается. Для запуска без переноса уберите этот флаг.

Сценарий использует `stack.jobs.yaml` и создаёт пять контейнеров с разными задачами:

| Сервис | Узел | Назначение | После запуска |
|---|---|---|---|
| `db` | manager | PostgreSQL | Работает |
| `migrate` | manager | Обновление таблиц базы | Завершён, код 0 |
| `collectstatic` | manager | Сбор статических файлов | Завершён, код 0 |
| `web` | worker | Django через Gunicorn | Работает |
| `nginx` | manager | HTTP и выдача статики | Работает |

Сначала запускается база, затем последовательно выполняются `migrate` и `collectstatic`, после них — `web` и Nginx. Два задания работают в режиме `replicated-job` и штатно завершаются. При ошибке подготовки приложение не запускается. Все три сервиса Django используют один образ, но разные команды запуска.

Сети `frontend` и `backend` с драйвером `overlay` связывают сервисы между узлами. Данные базы и статика сохраняются в томах `postgres_data` и `static_data`. Тома и два внешних контейнера узлов не входят в пять контейнеров приложения.

Сайт: [http://localhost:8082/](http://localhost:8082/). Используется заранее настроенный проброс порта управляющего узла `8082:8081`. После переноса работают прежние пользователи.

Проверка сервисов, заданий и размещения приложения:

```cmd
docker exec cloud-swarm-manager docker stack services cloud_platform
docker exec cloud-swarm-manager docker service ps cloud_platform_migrate --no-trunc
docker exec cloud-swarm-manager docker service ps cloud_platform_collectstatic --no-trunc
docker exec cloud-swarm-manager docker service ps cloud_platform_web --no-trunc
```

Для `db`, `web`, `nginx` ожидается `1/1`; для двух заданий — `Complete` и успешное завершение. Они не должны постоянно работать. `web` должен размещаться на `swarm-worker`.

Повторный запуск сценария останавливает `web` и Nginx, повторяет задачи подготовки для текущего образа и запускает приложение. Данные сохраняются, но возникает перерыв в работе. При изменении настроек Nginx обновите имя `nginx_jobs_v1` в обоих местах `stack.jobs.yaml`: объекты Docker Config неизменяемы.

## Тестирование и обслуживание

Автоматические тесты и журналы в режиме Compose:

```cmd
docker compose -f compose.yaml -f compose.deploy.yaml exec web python manage.py test courses -v 2
docker compose -f compose.yaml -f compose.deploy.yaml logs --tail 40 web nginx db
```

Тесты проверяют основные функции, права доступа и обработку видеоссылок. Django создаёт отдельную тестовую базу. Внешние видео и отображение страниц проверяются вручную в браузере.

Журналы Swarm доступны через `docker exec cloud-swarm-manager docker service logs --tail 40 cloud_platform_web`; вместо `web` можно указать `db`, `nginx`, `migrate` или `collectstatic`.

Перед обновлением создайте резервную копию. Пример для базы Compose с именами `cloud_user` и `cloud_platform`:

```cmd
if not exist backups mkdir backups
docker compose exec db pg_dump -U cloud_user -d cloud_platform -Fc -f /tmp/cloud_platform_backup.dump
docker compose cp db:/tmp/cloud_platform_backup.dump ./backups/cloud_platform_backup.dump
```

Для проверки архив восстанавливают через `pg_restore` в отдельную пустую базу и сравнивают данные. Том PostgreSQL не заменяет резервную копию. Обычная остановка Compose выполняется командой `docker compose stop`; параметр `down -v` удаляет тома с данными.

Для обновления Compose скачайте образ командой `docker compose -f compose.yaml -f compose.deploy.yaml pull web`, затем повторите команду запуска. Для Swarm используйте сценарий развёртывания.

## Основные файлы и автоматизация

| Файл или каталог | Назначение |
|---|---|
| `accounts/`, `courses/`, `config/` | Пользователи, учебные функции и настройки Django |
| `Dockerfile`, `docker/entrypoint.py` | Сборка образа и подготовка приложения при запуске Compose |
| `compose.yaml`, `compose.deploy.yaml` | Локальная сборка и запуск опубликованного образа |
| `compose.cluster.yaml`, `stack.jobs.yaml` | Настройки узлов и сервисов Swarm |
| `docker/deploy_swarm_jobs.py` | Порядок развёртывания и одноразовые задачи Swarm |
| `nginx/default.conf`, `nginx/swarm-jobs.conf` | Настройки Nginx для двух вариантов запуска |
| `.github/workflows/ci.yml` | Проверки, сборка и публикация образа |

Для публикации в GitHub Actions задаются переменная `DOCKERHUB_USERNAME` и секрет `DOCKERHUB_TOKEN`. После успешных проверок в `main` публикуются теги `latest` и идентификатор коммита. При проверке pull request публикация не выполняется.

Оба узла Swarm работают на одном компьютере: это учебная демонстрация кластера. База, статика и Nginx закреплены за manager, приложение — за worker. Такая схема не защищает от отказа компьютера и не содержит резервного экземпляра приложения. Для публичного размещения отдельно настраиваются внешний доступ, домен, HTTPS и параметры Django.
