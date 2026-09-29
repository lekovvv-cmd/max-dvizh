# MAX ДВИЖ

**ДВИЖ помогает компании превратить «куда-нибудь бы сходить» в конкретный совместный план.** Приоритетная аудитория — небольшие компании друзей, которые уже общаются в мессенджере и хотят организовать досуг в ближайшее время. Поиск места или события и согласование обычно происходят раздельно: варианты пересылают в чат и вручную выясняют, кто готов пойти. ДВИЖ объединяет поиск, отбор и подтверждение. Результатов интервью или измеренного эффекта в репозитории нет.

`Сигнал → реальные варианты → приватный выбор инициатора → запуск → приватные реакции друзей → совпадение → финальное подтверждение → ДВИЖ СОБРАЛСЯ`.

ДВИЖ **не мэтчит людей**: он собирает выполнимый совместный план. Автор выбирает компанию, время, занятие и условия, отмечает подходящие варианты и явно запускает движ. Друзья видят только отобранные варианты. Реакция «Пошёл бы» предварительна; место становится общим планом после отдельных подтверждений нужного числа участников. Регулярный сигнал создаёт такой же приватный раунд; рассылка компании всё равно требует запуска автором.

## Быстрый запуск

Нужны Docker Engine с Compose и свободные локальные порты из таблицы ниже. Из корня репозитория:

```sh
docker compose up --build
```

После запуска: [Mini App](http://localhost:8080), [API](http://localhost:8000/api/v1/health), [Swagger/OpenAPI](http://localhost:8000/docs). `GET /api/v1/health/ready` проверяет конфигурацию API и PostgreSQL. Compose запускает локальный `development` с `ALLOW_DEMO_AUTH=true` и создаёт схему миграциями; реальные MAX credentials для этого не нужны. Для других портов задайте `FRONTEND_PORT`, `BACKEND_PORT` или `POSTGRES_PORT` в локальном `.env` либо окружении перед запуском, например `FRONTEND_PORT=18080`. Если 8080 занят, убедитесь, что открыта страница именно контейнера.

| Компонент | Назначение | Порт хоста | Настройка |
| --- | --- | --- | --- |
| `frontend` | React/TypeScript Mini App, Vite build, nginx и прокси `/api/*` | 8080 | `FRONTEND_PORT` |
| `backend` | FastAPI, MAX webhook и миграции при старте | 8000 | `BACKEND_PORT` |
| `postgres` | Постоянное доменное состояние и outbox | 5432 | `POSTGRES_PORT` |
| `worker` | Отправка и повторы MAX-уведомлений из PostgreSQL outbox | не публикуется | — |
| `scheduler` | Регулярные сигналы и истечение состояний | не публикуется | — |
| `redis` | Необязательный временный кеш каталога | не публикуется | `--profile cache` и `REDIS_URL` |

Redis не нужен для сигналов, реакций или outbox. Для локального кеша задайте `REDIS_URL=redis://redis:6379/0` и запустите `docker compose --profile cache up --build`. Без Redis обращения к доступным провайдерам выполняются напрямую.

Остановить контейнеры, сохранив данные PostgreSQL: `docker compose down`. Повторный запуск: `docker compose up` (`--build` после изменений кода или зависимостей). Полностью удалить **локальные** данные PostgreSQL: `docker compose down -v`; это необратимо для Compose volume.

## Как проверить основной сценарий

В локальном Compose демопользователь по умолчанию — `anton`. В разделе «Компания» при URL с `?dev` доступен переключатель demo ID: `anton`, `lena`, `maxim` (это локальные имена без паролей). После смены ID страница перезагружается. Пользователь создаётся в PostgreSQL на первом запросе. Режим работает **только** при `APP_ENV=development` и `ALLOW_DEMO_AUTH=true`; в production `X-Demo-User` отклоняется.

1. Под `anton` создайте компанию и сохраните приглашение. В «Компании» с `?dev` переключитесь на `lena`; после перезагрузки у неё ещё нет компании, поэтому откройте сохранённую ссылку-приглашение. Затем через «Компанию» переключитесь на `maxim` и откройте ту же ссылку. Вернитесь к `anton` через переключатель уже вступившего пользователя.
2. Подайте сигнал для компании: конкретное занятие, будущее время, минимум 3 человека. Для результата нужен доступный реальный источник в выбранном городе/категории; каталог не заполняется фиктивными объектами. Получите `CHOOSING_CANDIDATES` с проверенными карточками либо честный `NO_SOURCE`/`PROVIDER_UNAVAILABLE`.
3. `anton` приватно отмечает подходящий вариант «Пошёл бы» и нажимает «Запустить движ». До запуска `lena` и `maxim` не видят этот раунд; после запуска видят только выбранные автором варианты (`COLLECTING_REACTIONS`).
4. Под `lena`, затем `maxim` отметьте **тот же** вариант «Пошёл бы». После достижения минимума реакций состояние — `AWAITING_CONFIRMATION`; чужие имена ещё не раскрываются.
5. Под каждым из трёх пользователей нажмите «Я в деле» на актуальном варианте. После минимума подтверждений состояние — `GATHERED`, карточка «ДВИЖ СОБРАЛСЯ» показывает подтвердивших участников.

Точный API-маршрут, запросы, ожидаемые состояния, troubleshooting и reset: [сценарий проверяющего](docs/EVALUATOR_SCENARIO.md). Отдельный `scripts.smoke_dvizh` проверяет этот путь на **одноразовой** development БД и живом KudaGo, создавая уникальные demo ID; результат зависит от доступности источника. Старый `POST /development/seed-demo/{group_id}` создаёт явно модельные данные только в development и **не** доказывает работу KudaGo/Geoapify или MAX; для проверки реального основного сценария его не используйте.

`NO_SOURCE` означает, что для запроса не нашлось подходящих данных; это не утверждение об отсутствии мест во всём городе. `PROVIDER_UNAVAILABLE` означает сбой источника. `UNVERIFIED` — неизвестная цена/условие, `NEAR` — небольшое отклонение с отдельным согласием. `EXPIRED`, `CANCELLED`, `NO_MATCH` закрывают неудавшийся раунд; `WAITLISTED` — личная очередь при заполненном варианте. Недоступность источника не превращается в выдуманное значение.

## Архитектура и работа с данными

Frontend обращается к FastAPI через nginx. PostgreSQL хранит пользователей (MAX ID/отображаемое имя), компании и членство, приглашения, сохранённые точки, сигналы, кандидатов, приватные реакции и подтверждения, webhook dedupe и очередь уведомлений. У кандидата ДВИЖа сохраняются `provider`, ID/тип объекта, `source_url` при наличии и снимок известных цены/времени/места; время `source_fetched_at` есть в нормализованном ответе провайдера и старом снимке плана, но **не** в таблице `dvizh_candidates`. Просто просмотренные объекты не создают постоянный каталог. Redis, если включён, временно кеширует запросы к KudaGo с TTL. Frontend локально хранит некоторые черновики и отметку о подсказках. Политика автоматического удаления истории и полного удаления аккаунта в MVP не заявлена.

Факт провайдера (название, опубликованные цена и время) отделён от расчёта приложения (расстояние, совместимость, слот), пользовательского ввода (сигнал, адрес, бюджет), неопределённого значения и явно помеченной `DEMO`/`MODEL` записи. Неизвестная цена отображается как неизвестная; временная ошибка источника отличается от `NO_SOURCE`. Доступ к приватным данным ограничен сервером, детали — в [архитектуре](docs/ARCHITECTURE.md) и [безопасности и данных](docs/SECURITY_AND_DATA.md).

Источники зависимостей: [frontend/package-lock.json](frontend/package-lock.json) и [backend/requirements.lock](backend/requirements.lock). Основной стек: React, TypeScript, Vite, MAX UI, FastAPI, SQLAlchemy, Alembic, PostgreSQL. Dockerfiles и `.dockerignore` есть для обеих сборок.

## Переменные окружения

Полный безопасный шаблон — [.env.example](.env.example). Значения `POSTGRES_*` и пример пароля в нём предназначены **только для локального Compose**. Compose формирует `DATABASE_URL` из `POSTGRES_*`; при отдельном deployment `DATABASE_URL` задают явно и одинаково API, worker, scheduler. `Да (prod)` означает обязательность для указанного production-процесса; остальные значения имеют дефолт либо нужны при включении интеграции.

| Переменная | Обязательна? / кем используется | Назначение и безопасное локальное значение |
| --- | --- | --- |
| `APP_ENV`, `ALLOW_DEMO_AUTH` | все backend-процессы | В Compose `development`/`true`; в production `production`/`false` |
| `APP_PROCESS` | отдельный backend deployment | `api`, `worker`, `scheduler`; Compose задаёт процессы командами |
| `DATABASE_URL` | да (prod): API, worker, scheduler | PostgreSQL URL; Compose собирает локальный URL автоматически |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT` | Compose/postgres | Локальная БД, учётная запись и опубликованный порт; сменить пароль вне dev |
| `BACKEND_PORT`, `FRONTEND_PORT`, `BACKEND_URL` | Compose/nginx | Порты хоста и upstream nginx (`http://backend:8000` локально) |
| `REDIS_URL` | нет: API, scheduler | Пусто без кеша; с профилем `cache` — `redis://redis:6379/0` |
| `MAX_BOT_TOKEN` | да (prod): worker; нужен для MAX auth и подписки | Секрет бота; пусто только для локального demo |
| `MAX_BOT_USERNAME`, `MAX_MINI_APP_URL` | нет: MAX ссылки/настройка | Реальный username нужен для deep links; Mini App URL регистрируется в MAX отдельно |
| `MAX_BOT_API_BASE` | нет: MAX client | По умолчанию `https://platform-api2.max.ru` |
| `MAX_WEBHOOK_URL`, `MAX_WEBHOOK_SECRET` | для CLI-подписки, не старта API | Публичный HTTPS callback и секрет; оба пусты локально |
| `KUDAGO_BASE_URL`, `KUDAGO_TIMEOUT_SECONDS`, `KUDAGO_MAX_PAGES` | нет: поиск | URL и лимиты KudaGo из `.env.example` |
| `GEOAPIFY_API_KEY`, `GEOAPIFY_BASE_URL`, `GEOAPIFY_TIMEOUT_SECONDS` | ключ необязателен: поиск/подсказки | Ключ только на сервере; без него места/подсказки ограничены |
| `LEISURE_SEARCH_DEADLINE_SECONDS`, `LEISURE_CACHE_TTL_SECONDS` | нет: поиск | Лимит ожидания и срок кеша |
| `NEAR_BUDGET_MAX_DELTA_RUB`, `PLACE_PLAN_DURATION_MINUTES` | нет: подбор | Лимит отклонения бюджета и длительность для мест |
| `MAX_INIT_DATA_MAX_AGE_SECONDS` | нет: MAX auth | Допустимый возраст подписанного initData |
| `AUTOSIGNAL_POLL_SECONDS`, `AUTOSIGNAL_LOOKAHEAD_DAYS` | нет: scheduler | Частота и горизонт регулярных сигналов |
| `OUTBOX_POLL_SECONDS`, `OUTBOX_RETRY_MAX_SECONDS` | нет: worker | Опрос outbox и предел задержки повтора |

## Внешние сервисы и интеграции

| Сервис | Роль и обязательность | Credentials и отказ / локальная проверка |
| --- | --- | --- |
| **MAX** | Production auth, бот, webhook, уведомления, deep links, контекст Mini App | Реальные `MAX_BOT_TOKEN`, webhook secret и публичный HTTPS нужны для полной проверки; задаются в окружении deployment, не в Git. Без них API и локальный demo работают, но MAX-вход/доставка не проверяются. Worker в production без токена не стартует. |
| **KudaGo** | Внешние события, часть мест и detail/revalidation | Ключ не нужен. Покрытие зависит от города, занятия и окна; при сбое честный `PROVIDER_UNAVAILABLE` либо пригодный кеш. Локально нужен сетевой доступ. |
| **Geoapify** | POI/места, поиск по названию, адресные подсказки и геопоиск | `GEOAPIFY_API_KEY` хранится только на сервере. Без ключа API стартует, но обычные места ограничены запасными источниками, autocomplete недоступен. |
| **PostgreSQL** | Обязательная постоянная БД | Compose поднимает локально; при недоступности readiness не проходит. Production credentials задаются в deployment. |
| **Redis** | Необязательный временный кеш | Локально запускается профилем `cache`; недоступность не блокирует API и не заменяется модельными данными. |

## API и MAX

База API — `/api/v1`; актуальная схема — [OpenAPI 3.1](docs/openapi.json), Swagger — `/docs`, проверочные запросы — [DATA-API.yaml](DATA-API.yaml). Пользовательские запросы требуют `X-MAX-Init-Data`; локальный demo принимает `X-Demo-User` только в development. MAX webhook (`POST /api/v1/integrations/max/webhook`) требует `X-Max-Bot-Api-Secret`; без настроенного секрета он закрыт (403). Публичный production API URL пока **NEEDS_TEAM_INPUT** и остаётся `base_url: null`.

Production API стартует с `DATABASE_URL` и `ALLOW_DEMO_AUTH=false`, даже если webhook ещё не настроен; пишет безопасное `max_webhook_not_configured`. Для подписки из `backend/` выполните `python -m app.modules.max_integration.subscribe_webhook` после задания `MAX_BOT_TOKEN`, публичного HTTPS `MAX_WEBHOOK_URL` и `MAX_WEBHOOK_SECRET`; команда проверяет конфигурацию до отправки. `python -m app.modules.max_integration.diagnose` делает безопасную проверку бота. Для полного MAX-прогона нужны реальный бот, HTTPS и тестовые MAX-аккаунты; их предоставляет команда. Порядок deployment и TLS: [DEPLOY_RELAXDEV.md](docs/DEPLOY_RELAXDEV.md).

## Известные ограничения MVP

Покрытие KudaGo/Geoapify зависит от города и категории; `ПК-клуб` и `Термы` скрыты без надёжного источника. Цена и часы могут быть неизвестны, наличие свободных мест не гарантируется. Бронирования и оплаты нет. Внешний провайдер может быть недоступен; синтетические места не подмешиваются как реальные. Локальный demo не проверяет доставку MAX. Production MAX требует credentials, публичный HTTPS и ручную проверку mobile/web. Встроенного rate limiting и полной политики удаления истории нет.

## Тесты и материалы для сдачи

```sh
npm --prefix frontend ci
npm --prefix frontend run check
cd backend
python -m pip install -r requirements.lock
python -m ruff check .
python -m ruff format --check .
python -m mypy app scripts
python -m pytest
```

Для полного `pytest` нужны `DATABASE_URL` и `TEST_DATABASE_URL`, указывающие на **отдельную тестовую PostgreSQL**: тесты блокировок пересоздают её таблицы. Подробности — в [TESTING.md](docs/TESTING.md). Метрики из БД доступны через `python -m app.scripts.product_metrics`: время `launch → first reaction/match/gathered`, отправленные review-уведомления и подтверждения. Это инструменты проверки гипотезы, не доказательство улучшения; определения — в [PRODUCT_METRICS.md](docs/PRODUCT_METRICS.md).

Текущие документы: [сценарий эксперта](docs/EVALUATOR_SCENARIO.md), [чек-лист сдачи](docs/SUBMISSION_CHECKLIST.md), [продукт](docs/PRODUCT.md), [архитектура](docs/ARCHITECTURE.md), [API](docs/API.md), [безопасность и данные](docs/SECURITY_AND_DATA.md), [содержание презентации](docs/PRESENTATION_CONTENT_CHECKLIST.md), [план пилота](docs/PILOT_PLAN.md). [Архив](docs/archive/README.md) и исторические заметки о редизайне не описывают текущий проверочный путь.
