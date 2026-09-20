# API и интеграции

## Контракт приложения

Все продуктовые маршруты имеют префикс `/api/v1`. Источник полного контракта — [openapi.json](openapi.json), генерируемый FastAPI. Во время работы доступны `/openapi.json` и `/docs`. [DATA-API.yaml](../DATA-API.yaml) содержит проверочные запросы и ожидаемые поля; сейчас в нём локальный адрес, демонстрационные заголовки и незаполненная команда (`TBD`). Перед сдачей нужны адрес deployment и данные проверки организатора.

| Маршруты | Назначение |
| --- | --- |
| `GET /health`, `GET /health/ready` | Жизнеспособность и готовность. |
| `GET /session` | Текущий пользователь. |
| `GET/POST /groups`, `POST /groups/join/{token}` | Компании и вход по ссылке. |
| `PUT /groups/{group_id}/city` | Смена города владельцем; возвращает счётчики затронутых объектов. |
| `GET/POST /locations`, `PATCH/DELETE /locations/{location_id}`, `POST /locations/{location_id}/default` | Личные точки. |
| `GET/POST /intents` | Собственные условия; разовый Intent. |
| `POST /signal-batches`, `PUT/DELETE /signal-batches/{batch_id}`, `POST /signal-batches/{batch_id}/refresh` | Атомарный пакет Сигнала и повторный поиск. |
| `POST /autosignals`, `PUT /autosignals/{intent_id}`, `POST /autosignals/{intent_id}/{action}` | Создание, редактирование, pause/resume/cancel. |
| `GET /offers`, `POST /offers/{offer_id}/accept`, `/reject`, `/cancel` | Все личные текущие приглашения и явные действия. |
| `GET /plans`, `GET /plans/{plan_id}` | Планы пользователя. |
| `GET /leisure/cities`, `POST /leisure/sync/{city_slug}` | Города и обращение к провайдеру. |
| `POST /development/seed-demo/{group_id}` | Явные модельные данные, только development. |

`GET /offers` охватывает все компании пользователя. `accepted_count` не включает `conditional_count`; оставшиеся места учитывают оба счётчика. Поля `can_accept` и `can_waitlist` определяют допустимые действия. Личный прогресс условного участника возвращается только ему. `GET /intents` включает собственное расписание и состояние проверки источника.

Неизвестное приглашение в Компанию возвращает `404`, явно истёкшее — `410`. Удаление используемой активным Сигналом точки возвращает `409`. Ответы Location содержат подпись адреса и default, но не координаты. Смена города принимает только актуальный город KudaGo; произвольный slug клиента не считается достоверным.

## MAX

Реализованная граница: официальный Bridge `https://st.max.ru/js/max-web-app.js`, серверная проверка initData, ссылки для открытия приложения, исходящие уведомления Bot API и пользовательская отправка плана через Bridge. Обработчика входящих сообщений бота в приложении нет.

- Клиент передаёт `window.WebApp.initData` в `X-MAX-Init-Data`. Backend проверяет единственный `hash`, сортированные декодированные параметры, двухэтапный HMAC-SHA256 и возраст `auth_date`.
- Компания связывается с чатом только из подписанного `CHAT` контекста; backend проверяет доступ бота через `GET /chats/{chatId}`. Синхронизация участников чата не заявлена.
- Ссылки имеют вид `https://max.ru/<bot>?startapp=<payload>`. Приглашения Компании используют непрозрачные токены, уведомления — `offer_<uuid>` и `plan_<uuid>`; приложение обрабатывает стартовый контекст.
- Worker отправляет `POST /messages?user_id=...` с заголовком `Authorization: <bot-token>`. Создаются уведомления о приглашении и подтверждённом плане, а не отдельная система напоминаний.
- Пользователь отправляет итоговый план через `window.WebApp.shareMaxContent({ text })`.

Для реальной проверки владелец регистрирует бота и Mini App в MAX Business, публикует приложение и API по HTTPS, задаёт `APP_ENV=production`, токен и username. Затем проходит [ручной сценарий](TESTING.md) в MAX mobile и web, включая переходы из бота, уведомление и отправку плана. Локальная демонстрация не подтверждает доставку MAX.

Перед сдачей следует сверить [Bridge](https://dev.max.ru/docs/webapps/bridge), [валидацию](https://dev.max.ru/docs/webapps/validation), [Mini App](https://dev.max.ru/docs/webapps/introduction) и [Bot API](https://dev.max.ru/docs-api) с актуальными правилами платформы. Последняя записанная в проекте проверка интеграционных контрактов — 18 сентября 2026; наличие кода не означает прохождение внешнего deployment QA.

## KudaGo

Backend-адаптер использует публичный API v1.4: города, категории, Events с местом и отдельные Places. Есть таймаут, ограниченная пагинация, нормализация дат, цены, координат и источника. Событию не придумывается конец; закрытые или неподходящие места не становятся обычными предложениями.

Внутренние категории отображаются на категории провайдера. Для «Бани и спа» код использует `salons`, `suburb`, `recreation`, `amusement` и дополнительный поиск тематических слов в названии/описании, чтобы исключить обычные салоны красоты. Это правило адаптера, а не отдельная категория KudaGo.

Ключ Redis зависит от города, начала/конца окна и набора категорий; TTL по умолчанию 900 секунд. Действующий кеш допускается при недоступности источника, без него возвращается состояние недоступности. Автоматической подмены модельными данными нет. Политика цены и происхождения данных — в [SECURITY_AND_DATA.md](SECURITY_AND_DATA.md); справочник источника — [KudaGo API](https://docs.kudago.com/api/).

## Параметры окружения

Без `.env` Compose запускает локальное окружение. Для изменения значений скопируйте [.env.example](../.env.example). Значения секретов задаются отдельно при deployment.

| Параметр | Значение по умолчанию / назначение |
| --- | --- |
| `APP_ENV` | `development`; только этот режим разрешает `X-Demo-User`. На deployment — `production`. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Локальные `max_dvizh`, `max_dvizh`, `local_development_only`; сменить при deployment. |
| `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT` | `5432`, `8000`, `8080`. |
| `DATABASE_URL` | Для запуска backend вне Compose. Compose составляет URL из `POSTGRES_*`. |
| `REDIS_URL` | Для запуска вне Compose; Compose фиксирует `redis://redis:6379/0`. |
| `MAX_BOT_TOKEN`, `MAX_BOT_USERNAME` | Секрет бота и публичное имя для ссылок. По умолчанию пустые. |
| `MAX_BOT_API_BASE` | `https://platform-api2.max.ru`. |
| `MAX_MINI_APP_URL` | Сейчас только читается в Settings и не используется для ссылок. Реальный HTTPS URL регистрируется в MAX Business. |
| `MAX_INIT_DATA_MAX_AGE_SECONDS` | `3600`, допустимый возраст запуска. |
| `KUDAGO_BASE_URL` | `https://kudago.com/public-api/v1.4`. |
| `KUDAGO_TIMEOUT_SECONDS`, `KUDAGO_MAX_PAGES` | `5` секунд, до `3` страниц. |
| `LEISURE_CACHE_TTL_SECONDS` | `900`. |
| `NEAR_BUDGET_MAX_DELTA_RUB` | `150`. |
| `PLACE_PLAN_DURATION_MINUTES` | `120`. |
| `AUTOSIGNAL_POLL_SECONDS`, `AUTOSIGNAL_LOOKAHEAD_DAYS` | `1800` и `7`, передаются scheduler. |
| `OUTBOX_POLL_SECONDS`, `OUTBOX_RETRY_MAX_SECONDS` | `5` и `300`. |

Compose — локальная конфигурация, не готовая HTTPS-инфраструктура. Reverse proxy, сертификаты и доступы настраиваются при deployment. Версии установок фиксируются `frontend/package-lock.json` и `backend/requirements.lock`.
