# Deployment на RelaxDev

Актуальные руководства RelaxDev подтверждают `rootDir` для монорепозитория, отдельный
проект на каждый Docker-сервис, долгоживущие фоновые процессы, управляемые PostgreSQL
и Redis: [общая документация](https://relaxdev.ru/docs),
[Docker](https://relaxdev.ru/deploy/docker),
[Python и фоновые процессы](https://relaxdev.ru/deploy/python). Docker Compose на
платформе не запускается: он остаётся локальным сценарием проекта.

## Проекты

Во всех четырёх проектах выберите GitHub-репозиторий
`lekovvv-cmd/max-dvizh`, ветку `main`, режим собственного Dockerfile и включите
автодеплой.

| Проект | Root directory | Dockerfile | Процесс |
| --- | --- | --- | --- |
| `dvizh-frontend` | `frontend/` | `frontend/Dockerfile` | nginx из `CMD` образа |
| `dvizh-api` | `backend/` | `backend/Dockerfile` | `APP_PROCESS=api` (значение по умолчанию) |
| `dvizh-worker` | `backend/` | `backend/Dockerfile` | `APP_PROCESS=worker` |
| `dvizh-scheduler` | `backend/` | `backend/Dockerfile` | `APP_PROCESS=scheduler` |

Публичная документация RelaxDev не описывает override `CMD` для Docker-проекта.
Поэтому команду запуска в панели переопределять не нужно: один backend-образ выбирает
процесс через `APP_PROCESS`. Фактические команды образа:

- API: `alembic upgrade head`, затем
  `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`;
- worker: `python -m app.modules.max_integration.worker`;
- scheduler: `python -m app.modules.matching.scheduler`.

RelaxDev передаёт веб-контейнеру `PORT=8080`. API и nginx читают `PORT`; локально без
него используют `8000` и `8080` соответственно. Worker и scheduler не принимают
входящий HTTP-трафик и работают как отдельные долгоживущие процессы.

## PostgreSQL и Redis

1. В проекте `dvizh-api` создайте PostgreSQL в разделе «База данных». Платформа
   добавит `DATABASE_URL`.
2. Подключите управляемый Redis к той же команде и проекту. Платформа добавит
   `REDIS_URL`.
3. Скопируйте **те же** `DATABASE_URL` и `REDIS_URL` в переменные `dvizh-worker` и
   `dvizh-scheduler`. Все три backend-процесса должны использовать одну БД и один Redis.

Документация не фиксирует текстовую схему выдаваемого PostgreSQL URL. Приложение
принимает `postgres://`, `postgresql://` и уже явный `postgresql+psycopg://`, выбирая
драйвер psycopg 3 только на конфигурационной границе. `REDIS_URL` передаётся в
`redis-py` без изменения. Не открывайте внешние порты БД или Redis без отдельной
необходимости.

## Переменные проектов

Секреты задаются только в панели RelaxDev. Значения с дефолтами можно не добавлять,
если дефолт подходит production.

`dvizh-frontend`:

```dotenv
BACKEND_URL=https://<api-project-domain>
```

URL должен быть origin без завершающего `/`. Nginx сохраняет исходный путь `/api/*`,
Host/SNI HTTPS-upstream и forwarded-заголовки. CORS не нужен: браузер обращается к
same-origin `/api/*` frontend-проекта.

`dvizh-api`:

```dotenv
APP_ENV=production
APP_PROCESS=api
ALLOW_DEMO_AUTH=false
DATABASE_URL=<from RelaxDev>
REDIS_URL=<from RelaxDev>
MAX_BOT_TOKEN=<secret>
MAX_BOT_USERNAME=<bot username>
MAX_BOT_API_BASE=https://platform-api2.max.ru
MAX_WEBHOOK_URL=https://<api-project-domain>/api/v1/integrations/max/webhook
MAX_WEBHOOK_SECRET=<random secret 5-256 permitted characters>
KUDAGO_BASE_URL=https://kudago.com/public-api/v1.4
KUDAGO_TIMEOUT_SECONDS=5
KUDAGO_MAX_PAGES=3
LEISURE_CACHE_TTL_SECONDS=900
NEAR_BUDGET_MAX_DELTA_RUB=150
PLACE_PLAN_DURATION_MINUTES=120
MAX_INIT_DATA_MAX_AGE_SECONDS=3600
```

`dvizh-worker`:

```dotenv
APP_ENV=production
APP_PROCESS=worker
DATABASE_URL=<same as API>
REDIS_URL=<same as API>
MAX_BOT_TOKEN=<secret>
MAX_BOT_USERNAME=<bot username>
MAX_BOT_API_BASE=https://platform-api2.max.ru
MAX_WEBHOOK_URL=https://<api-project-domain>/api/v1/integrations/max/webhook
MAX_WEBHOOK_SECRET=<same secret as API>
KUDAGO_BASE_URL=https://kudago.com/public-api/v1.4
KUDAGO_TIMEOUT_SECONDS=5
KUDAGO_MAX_PAGES=3
LEISURE_CACHE_TTL_SECONDS=900
NEAR_BUDGET_MAX_DELTA_RUB=150
PLACE_PLAN_DURATION_MINUTES=120
MAX_INIT_DATA_MAX_AGE_SECONDS=3600
OUTBOX_POLL_SECONDS=5
OUTBOX_RETRY_MAX_SECONDS=300
```

`dvizh-scheduler`:

```dotenv
APP_ENV=production
APP_PROCESS=scheduler
DATABASE_URL=<same as API>
REDIS_URL=<same as API>
KUDAGO_BASE_URL=https://kudago.com/public-api/v1.4
KUDAGO_TIMEOUT_SECONDS=5
KUDAGO_MAX_PAGES=3
LEISURE_CACHE_TTL_SECONDS=900
NEAR_BUDGET_MAX_DELTA_RUB=150
PLACE_PLAN_DURATION_MINUTES=120
AUTOSIGNAL_POLL_SECONDS=1800
AUTOSIGNAL_LOOKAHEAD_DAYS=7
```

`PORT` вручную не задавайте: это служебная переменная RelaxDev. `MAX_MINI_APP_URL`
текущая продуктовая логика не использует; публичный URL Mini App регистрируется в MAX
отдельно.

## Порядок запуска и проверка

1. Сначала разверните `dvizh-api` с PostgreSQL и Redis. Убедитесь, что миграции
   завершились и контейнер не перезапускается.
2. Подставьте публичный HTTPS origin API в `BACKEND_URL` проекта `dvizh-frontend` и
   разверните frontend.
3. Разверните worker и scheduler с общими URL ресурсов.
4. После готовности публичного HTTPS API выполните в среде API (или в локальном shell с теми же секретами): `python -m app.modules.max_integration.subscribe_webhook`. Команда делает POST `/subscriptions` и проверяет GET `/subscriptions`. Повторите её при смене домена или секрета. В production используйте только Webhook, не запускайте Long Polling.
5. Проверьте:

```text
https://<api-project-domain>/api/v1/health
https://<api-project-domain>/api/v1/health/ready
https://<frontend-project-domain>/
https://<frontend-project-domain>/api/v1/health
```

Проверьте также, что `GET /api/v1/session` с заголовком
`X-Demo-User: test` возвращает `401`. Ответ `200` означает, что включён
локальный демо-вход: установите `ALLOW_DEMO_AUTH=false` и передеплойте API.

Последний запрос должен вернуть ответ API через nginx frontend-проекта. После проверки
передайте владельцу MAX-бота публичный HTTPS URL frontend:
`https://<frontend-project-domain>`.

## Что копировать из панели RelaxDev

```dotenv
DATABASE_URL=<from RelaxDev>
REDIS_URL=<from RelaxDev>
BACKEND_URL=https://<api-project-domain>
MAX_BOT_TOKEN=<secret>
MAX_BOT_USERNAME=<bot username>
MAX_WEBHOOK_URL=https://<api-project-domain>/api/v1/integrations/max/webhook
MAX_WEBHOOK_SECRET=<secret>
```

Также сохраните поля `dvizh-api` domain и `dvizh-frontend` domain. Они появляются
только после создания проектов; реальные домены, токены и credentials в git не
добавляются.
