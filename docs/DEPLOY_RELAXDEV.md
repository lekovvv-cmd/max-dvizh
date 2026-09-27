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
2. Скопируйте **тот же** `DATABASE_URL` в переменные `dvizh-worker` и
   `dvizh-scheduler`. Все три backend-процесса должны использовать одну БД.
   В production без явно заданного `DATABASE_URL` процесс завершится; локальный
   адрес `postgres` подставляется только при `APP_ENV=development`.
3. Redis — необязательный кеш каталога KudaGo. Без `REDIS_URL` приложение обращается
   к провайдеру напрямую; недоступность кеша не останавливает API или scheduler.
   Если кеш нужен, подключите Redis и передайте его `REDIS_URL` API и scheduler.
   Worker работает с outbox в PostgreSQL и Redis не требует.

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
# Optional; omit to run without cache
REDIS_URL=
MAX_BOT_TOKEN=<secret>
MAX_BOT_USERNAME=<actual bot username>
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
MAX_BOT_TOKEN=<secret>
MAX_BOT_USERNAME=<same as API>
MAX_BOT_API_BASE=https://platform-api2.max.ru
OUTBOX_POLL_SECONDS=5
OUTBOX_RETRY_MAX_SECONDS=300
```

`dvizh-scheduler`:

```dotenv
APP_ENV=production
APP_PROCESS=scheduler
DATABASE_URL=<same as API>
# Optional; same cache as API if enabled
REDIS_URL=
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

API в production проверяет `MAX_BOT_TOKEN`, HTTPS `MAX_WEBHOOK_URL` и
`MAX_WEBHOOK_SECRET` до запуска. Секрет: 5–256 символов `A-Z a-z 0-9 _ -`.
`MAX_BOT_USERNAME` нужен для ссылок в Mini App и приглашений: без него API
запускается с предупреждением `max_deep_links_disabled`, ссылки недоступны.
Worker требует токен, но не webhook URL/secret. Scheduler требует БД, но не
настройки MAX. Во всех production-процессах оставьте `ALLOW_DEMO_AUTH=false`.

## Порядок запуска и проверка

1. Сначала разверните `dvizh-api` с PostgreSQL. Убедитесь, что миграции
   завершились и контейнер не перезапускается.
2. Подставьте публичный HTTPS origin API в `BACKEND_URL` проекта `dvizh-frontend` и
   разверните frontend.
3. Разверните worker и scheduler с тем же `DATABASE_URL`, что у API.
   Scheduler проверяет соединение при старте и пишет
   `scheduler_started mode=production database_connected=true` без адреса и пароля БД.
   В логах worker должна появиться строка `outbox_worker_started`, затем раз в минуту
   `outbox_heartbeat`. Если `MAX_BOT_TOKEN` не задан, worker завершится с явной ошибкой.
   После запуска тестового движа проверьте `outbox_sent kind=DVIZH_REVIEW_REQUIRED`
   для других участников компании. `outbox_delivery_failed` содержит HTTP-статус
   ответа MAX и число попыток, без токена и текста сообщения. Если heartbeat есть,
   а `pending` растёт, проверьте токен, доступ к MAX API и общую базу с API.
4. После готовности публичного HTTPS API выполните в среде API (или в shell с теми же секретами): `python -m app.modules.max_integration.subscribe_webhook`. Команда делает POST `/subscriptions` (создание/обновление подписки по URL), затем проверяет URL и типы `bot_started`, `message_callback`, `bot_removed` через GET `/subscriptions`. Повторный запуск обновляет ту же подписку; повторите его при смене секрета. GET не возвращает секрет, поэтому успешная проверка URL/типов не доказывает доставку webhook. При смене домена отдельно удалите старую подписку через MAX API. В production используйте только Webhook, не запускайте Long Polling.
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

`/health/ready` проверяет настройки API и доступность БД. Он не проверяет токен у
MAX, внешнюю доставку webhook или уведомления. Эти проверки выполняются отдельно.

Запрос к `/api/v1/health` на frontend-домене должен вернуть ответ API через nginx.
После проверки передайте владельцу MAX-бота публичный HTTPS URL frontend:
`https://<frontend-project-domain>`.

## Диагностика MAX

В среде worker выполните `python -m app.modules.max_integration.diagnose`.
Команда показывает API base и факт наличия токена, делает только GET `/me`,
возвращает ненулевой код при ошибке и не отправляет сообщения пользователям.
Токен, MAX ID, тела личных сообщений и сырые ответы не выводятся.

В `outbox_delivery_failed` есть ID outbox, kind, попытка, статус, endpoint и
класс исключения (`error_class`). Поле `reason` различает `tls`, `dns`,
`connect_timeout`, `read_timeout`, `timeout`, `connect`, `transport`, HTTP-код
(`http_401`, `http_429` и т. д.) или `invalid_recipient`. Безопасный
фрагмент ответа содержит только известный машинный код ошибки, прочее опускается.
Сеть, 429 и 5xx повторяются с задержкой, максимум 8 попыток; остальные 4xx
завершаются `FAILED`, устаревшие уведомления — `CANCELLED`. `bot_started`
возобновляет только ещё актуальные failed-уведомления этого пользователя.

При TLS-ошибке проверьте цепочку доверия в образе и `SSL_CERT_FILE`/`SSL_CERT_DIR`.
Не отключайте проверку сертификата. Согласно [документации MAX](https://dev.max.ru/docs-api),
`platform-api2.max.ru` требует доверия к сертификатам Минцифры; настройки доверия
проверяются в фактической среде deployment. При DNS/connect проверьте DNS и исходящий
HTTPS; при 401/403 — токен/права, при invalid recipient — доступность получателя боту.
Официальные контракты: [GET /me](https://dev.max.ru/docs-api/methods/GET/me),
[POST /subscriptions](https://dev.max.ru/docs-api/methods/POST/subscriptions),
[GET /subscriptions](https://dev.max.ru/docs-api/methods/GET/subscriptions).

## Что копировать из панели RelaxDev

```dotenv
DATABASE_URL=<from RelaxDev>
REDIS_URL=<optional cache URL, otherwise empty>
BACKEND_URL=https://<api-project-domain>
MAX_BOT_TOKEN=<secret>
MAX_BOT_USERNAME=<bot username>
MAX_WEBHOOK_URL=https://<api-project-domain>/api/v1/integrations/max/webhook
MAX_WEBHOOK_SECRET=<secret>
```

Также сохраните поля `dvizh-api` domain и `dvizh-frontend` domain. Они появляются
только после создания проектов; реальные домены, токены и credentials в git не
добавляются.
