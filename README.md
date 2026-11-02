# Платформа управления дистанционными образовательными курсами

Учебный проект по теме «Настройка и администрирование облачной платформы для управления дистанционными образовательными курсами».

Клиент-серверное приложение для публикации курсов, просмотра учебных материалов и вебинаров, отправки ответов на задания и проверки работ преподавателем.

- [Исходный код](https://github.com/2beerCOOLez-dif/cloud-platform)
- [Образ приложения в Docker Hub](https://hub.docker.com/r/2beercoolez1/cloud-platform)
- [Автоматические проверки и публикация](https://github.com/2beerCOOLez-dif/cloud-platform/actions)

## Возможности

| Роль | Возможности |
|---|---|
| Студент | Поиск опубликованных курсов, запись на обучение, просмотр уроков и видео, отправка текстового ответа, просмотр оценки и комментария |
| Преподаватель | Управление своими курсами, уроками и заданиями, просмотр ответов студентов, выставление и изменение оценок |
| Администратор | Управление пользователями, ролями и данными через административную панель Django |

Пользователей создаёт администратор. Публичная регистрация не реализована. На одно задание студент отправляет один ответ; после отправки изменить его через сайт нельзя. Оценка выставляется по шкале от 0 до 100.

Материалы опубликованного курса доступны записанным студентам, преподавателю этого курса и администратору. Преподаватель управляет материалами своих черновиков через личный кабинет.

К уроку можно прикрепить ссылку на YouTube, Rutube или Vimeo. Встроенный плеер загружается без автоматического воспроизведения, с первоначально выключенным звуком. Для просмотра необходимы доступность видеоплощадки и разрешение автора на встраивание.

## Технологии и устройство

| Компонент | Технологии и назначение |
|---|---|
| Интерфейс | HTML, CSS, JavaScript и шаблоны Django |
| Приложение | Python 3.12, Django 5.2, Gunicorn 26 |
| Данные | PostgreSQL 17 |
| Веб-сервер | Nginx |
| Развёртывание | Docker и Docker Compose |
| Проверки и доставка | GitHub Actions и Docker Hub |

Compose запускает три сервиса:

- `nginx` принимает запросы браузера на локальном порту `8081` и выдаёт статические файлы.
- `web` запускает Django через Gunicorn на внутреннем порту `8000`.
- `db` хранит данные в PostgreSQL на внутреннем порту `5432`.

Приложение обращается к PostgreSQL по имени `db`. Сеть `backend` связывает приложение с базой; сеть `frontend` связывает Nginx с приложением.

Том `postgres_data` сохраняет базу между пересозданиями контейнеров. Том `static_data` содержит собранные CSS и JavaScript. Том с данными не заменяет резервную копию.

## Запуск из Docker Hub

Команды ниже предназначены для PowerShell. Выполняйте их из корня репозитория. Для запуска контейнеров нужны Git, Docker и Docker Compose v2; устанавливать Python на компьютере не требуется. В Windows Docker Desktop должен работать в режиме Linux-контейнеров.

### Первоначальная подготовка

Клонируйте репозиторий:

~~~powershell
git clone https://github.com/2beerCOOLez-dif/cloud-platform.git
cd cloud-platform
~~~

В новом каталоге создайте настройки из образца:

~~~powershell
Copy-Item .env.example .env
~~~

Если `.env` уже существует, сохраните его настройки вместо повторного копирования образца.

Откройте `.env` и замените значения `POSTGRES_PASSWORD` и `DJANGO_SECRET_KEY`. Случайное значение секретного ключа можно получить через Docker:

~~~powershell
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
~~~

| Переменная | Назначение |
|---|---|
| `POSTGRES_DB` | Имя базы; в примере `cloud_platform` |
| `POSTGRES_USER` | Пользователь PostgreSQL; в примере `cloud_user` |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL |
| `DJANGO_SECRET_KEY` | Секретный ключ Django |
| `DJANGO_DEBUG` | В контейнерном запуске `False` |
| `DJANGO_ALLOWED_HOSTS` | Разрешённые имена хостов; по умолчанию `localhost,127.0.0.1` |
| `DB_HOST`, `DB_PORT` | Параметры запуска Django с компьютера; внутри контейнера переопределяются на `db` и `5432` |
| `APP_VERSION` | Необязательный тег образа; по умолчанию `latest` |

Файл `.env` и папка `backups/` исключены из Git. Шаблон `.env.example` содержит только примеры настроек.

### Запуск одной командой

После подготовки файлов и настроек:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml up -d --no-build --pull always --wait --wait-timeout 180
~~~

Команда скачивает готовые образы и запускает сервисы без локальной сборки приложения. При старте `web` автоматически применяются миграции и выполняется `collectstatic`.

Проверьте состояние:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml ps
~~~

Все три сервиса должны иметь состояние `healthy`.

- Сайт: http://localhost:8081/
- Административная панель: http://localhost:8081/admin/
- Вход пользователей: http://localhost:8081/accounts/login/

### Первый администратор и пользователи

На новой пустой базе создайте администратора:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml exec web python manage.py createsuperuser
~~~

В административной панели создайте преподавателей и студентов и назначьте им соответствующие роли. Обычным преподавателям и студентам административные флаги `is_staff` и `is_superuser` не требуются.

Преподаватель создаёт курс, добавляет уроки и задания и публикует курс. Студент записывается через каталог и получает доступ к материалам. Ответы проверяются преподавателем из страницы управления курсом.

## Управление и обновление

Остановить сервисы с сохранением данных:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml stop
~~~

Запустить снова, используя имеющиеся образы:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml up -d --no-build --wait
~~~

Посмотреть последние сообщения журналов:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml logs --tail 80 web nginx db
~~~

Обновить файлы проекта и скачать опубликованные образы:

~~~powershell
git pull --ff-only
docker compose -f compose.yaml -f compose.deploy.yaml up -d --no-build --pull always --wait --wait-timeout 180
~~~

Перед обновлением сохраните локальные изменения и создайте резервную копию базы. Для выбора конкретной версии укажите в `.env` значение `APP_VERSION`, равное тегу коммита из Docker Hub. Смена тега приложения сама по себе не откатывает миграции и данные.

Не используйте `docker compose down -v` для обычной остановки: параметр `-v` удаляет тома, включая базу данных.

## Локальная сборка

Для проверки изменений исходного кода:

~~~powershell
docker compose up -d --build --wait --wait-timeout 180
~~~

В этом режиме Compose собирает приложение по Dockerfile. После изменения Python, шаблонов, CSS или JavaScript повторите команду сборки. Одновременный запуск двух режимов в одной папке не создаёт две независимые платформы: они используют один Compose-проект и его тома.

## Проверки

Запуск автоматических тестов внутри опубликованного образа:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml exec web python manage.py test courses -v 2
~~~

В проекте 20 тестов. Проверяются вход и выход, публикация курсов, доступ к материалам, права владельца курса, запись на обучение, отправка и конфиденциальность ответов, выставление оценок, CSRF-защита и разбор видеоссылок.

Django создаёт отдельную тестовую базу и удаляет её после выполнения. Учётная запись тестовой базы должна иметь право создавать базы данных; пользователь, созданный текущим образом PostgreSQL через `POSTGRES_USER`, имеет необходимые права.

Проверка конфигурации Nginx:

~~~powershell
docker compose -f compose.yaml -f compose.deploy.yaml exec nginx nginx -t
~~~

Воспроизведение внешних видео и внешний вид страниц проверяются в браузере: Django Test Client не исполняет JavaScript.

## Резервное копирование и проверка восстановления

Примеры используют пользователя `cloud_user` и базу `cloud_platform`. Если значения изменены в `.env`, подставьте свои имена.

Все команды выполняются из прежней папки проекта. Короткие команды `docker compose exec` и `docker compose cp` обращаются к сервисам этого же Compose-проекта.

### Создание копии

~~~powershell
New-Item -ItemType Directory -Force backups
docker compose exec db pg_dump -U cloud_user -d cloud_platform -Fc -f /tmp/cloud_platform_backup.dump
docker compose cp db:/tmp/cloud_platform_backup.dump ./backups/cloud_platform_backup.dump
Get-Item .\backups\cloud_platform_backup.dump
~~~

Архив создаётся внутри контейнера и копируется как файл: двоичное содержимое не проходит через текстовое перенаправление PowerShell. Храните копии за пределами тома PostgreSQL; для нескольких дат используйте разные имена файлов.

`pg_dump` сохраняет выбранную базу, но не глобальные роли всего PostgreSQL. В приведённом сценарии роль `cloud_user` уже существует благодаря инициализации контейнера.

### Восстановление в отдельную базу

~~~powershell
docker compose cp ./backups/cloud_platform_backup.dump db:/tmp/restore_check.dump
docker compose exec db createdb -U cloud_user -T template0 cloud_platform_restore_check
docker compose exec db pg_restore -U cloud_user -d cloud_platform_restore_check --no-owner --no-privileges --exit-on-error --single-transaction /tmp/restore_check.dump
~~~

Проверочная база должна быть новой и пустой. Восстановление направлено в `cloud_platform_restore_check`; рабочая база `cloud_platform` не перезаписывается.

### Сравнение восстановленных данных

Чтобы сравнение соответствовало состоянию копии, от её создания до конца проверки не изменяйте учебные данные и не выполняйте новые входы пользователей.

В PowerShell передайте код через стандартный ввод:

~~~powershell
@'
from copy import deepcopy
from django.contrib.auth import get_user_model
from django.db import connections
from courses.models import Course, Lesson, Enrollment, Assignment, Submission

config = deepcopy(connections["default"].settings_dict)
config["NAME"] = "cloud_platform_restore_check"
connections.databases["restore_check"] = config

models = [
    get_user_model(),
    Course,
    Lesson,
    Enrollment,
    Assignment,
    Submission,
]

try:
    for model in models:
        source = list(model.objects.using("default").order_by("pk").values())
        restored = list(model.objects.using("restore_check").order_by("pk").values())
        matches = source == restored
        print(f"{model._meta.label}: count={len(source)}, match={matches}")
        if not matches:
            raise RuntimeError(f"Data mismatch: {model._meta.label}")
finally:
    connections["restore_check"].close()

print("Restore verification passed.")
'@ | docker compose exec -T web python manage.py shell
~~~

У всех шести моделей должно быть `match=True`, затем — `Restore verification passed.`. Сравниваются значения полей, включая тексты ответов, оценки и видеоссылки; содержимое записей не выводится на экран.

После успешной проверки удалите только проверочную базу:

~~~powershell
docker compose exec db dropdb -U cloud_user cloud_platform_restore_check
~~~

Сохранённый архив остаётся в `backups/`.

## Автоматизация GitHub Actions

Файл [.github/workflows/ci.yml](.github/workflows/ci.yml) запускает:

1. Проверку настроек Django и наличия миграций.
2. Тесты с временной базой PostgreSQL.
3. После успешных проверок в `main` — сборку и публикацию образа приложения.

В pull request выполняются только проверки. После push в `main` или ручного запуска из `main` публикуются теги `latest` и полный идентификатор коммита.

Настройки репозитория GitHub в разделе **Settings → Secrets and variables → Actions**:

| Тип | Имя | Значение |
|---|---|---|
| Variable | `DOCKERHUB_USERNAME` | Docker ID владельца репозитория образов |
| Secret | `DOCKERHUB_TOKEN` | Токен Docker Hub с правом публикации |

Текущий репозиторий образов: `2beercoolez1/cloud-platform`. Workflow проверяет код и доставляет образ; запуск на целевой машине выполняется командой Compose.

## Структура репозитория

| Путь | Назначение |
|---|---|
| `accounts/` | Пользователи, роли, вход и личный кабинет |
| `courses/` | Курсы, уроки, задания, ответы, оценки и вебинары |
| `config/` | Настройки Django и корневые маршруты |
| `docker/entrypoint.py` | Применение миграций, сбор статики и запуск сервера |
| `nginx/default.conf` | Обратное проксирование и выдача статики |
| `Dockerfile` | Сборка образа приложения |
| `compose.yaml` | Сервисы, сети, тома и локальная сборка |
| `compose.deploy.yaml` | Выбор опубликованного образа |
| `.env.example` | Образец настроек без настоящих секретов |
| `courses/tests.py` | Автоматические тесты |

## Область применения

Текущая конфигурация предназначена для локальной демонстрации и привязана к `127.0.0.1:8081`. Для публичного размещения на сервере отдельно настраиваются внешний доступ, домен, HTTPS и соответствующие параметры Django.

Реализованы переносимый контейнерный запуск и автоматическая доставка образа. Многоузловой кластер и автоматическое развёртывание на облачном сервере в текущую реализацию не входят.

