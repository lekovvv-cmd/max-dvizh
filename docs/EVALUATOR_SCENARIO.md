# Сценарий проверки MAX ДВИЖ

## Предусловия и запуск

Из корня чистого clone запустите `docker compose up --build -d`, затем `docker compose exec backend python -m scripts.seed_demo`. Локальный Compose включает `APP_ENV=development` и `ALLOW_DEMO_AUTH=true`; MAX-токен не нужен. Seed заранее создаёт компанию и участников, повторный запуск ничего не дублирует. Дождитесь `GET http://localhost:8000/api/v1/health/ready` → `{"status":"ready","database":"ok"}`. Откройте `http://localhost:8080/?dev` и `http://localhost:8080/api/v1/health/ready`: второй адрес проверяет nginx → backend. Swagger: `http://localhost:8000/docs`.

Если 8080 занят, перед запуском задайте `FRONTEND_PORT=18080` и используйте `http://localhost:18080`. Состояние контейнеров: `docker compose ps`; нужны `postgres`, `backend`, `worker`, `scheduler`, `frontend`.

## Demo-пользователи и компания

Локальные ID: `anton` (инициатор), `lena` и `maxim` (участники). Это не аккаунты MAX и у них нет паролей. Seed создаёт `Demo company` в `msk`, включает всех троих и печатает динамические UUID. В браузере по умолчанию открыт `anton`; в «Компании» по URL `http://localhost:8080/?dev` доступен переключатель ID. После смены страница перезагружается. API принимает заголовок `X-Demo-User: anton|lena|maxim` только в development. Формальное описание набора: [test-data.json](test-data.json). При ручном API-прогоне получите `group_id` из `GET /api/v1/groups` под `anton`; не подставляйте фиксированный UUID. Не используйте production БД для этой проверки.

## Основной сценарий и ожидаемые состояния

1. Под `anton` выберите готовую `Demo company`, занятие из `GET /api/v1/leisure/taxonomy`, будущее окно и минимум 3 участников. `POST /api/v1/signals` принимает `group_ids`, `activity_categories`, `available_from`, `available_to`, `min_people`; желательно передать уникальный `X-Request-ID`. Ответ содержит `signal_batch_id` и `dvizhi[]` с новыми ID. Подтверждённый пересекающийся движ даёт `409 SCHEDULE_CONFLICT` ещё до запроса к провайдеру, без нового раунда.
2. Если доступны реальные записи провайдера, `dvizhi[0].status=CHOOSING_CANDIDATES`, `candidates[]` содержит провайдера и доступные факты источника. Если записей нет — `NO_SOURCE`; при временном сбое — `PROVIDER_UNAVAILABLE`. Смените занятие/город/окно или повторите поиск после восстановления источника. Эти состояния не следует подменять demo-объектами.
3. До запуска `GET /api/v1/dvizhi/{id}` от `lena`/`maxim` возвращает 404. `anton` отмечает один подходящий `candidate_id` через `PUT /api/v1/dvizhi/{id}/candidates/{candidate_id}/reaction` с `{"value":"WOULD_GO"}` и делает `POST /api/v1/dvizhi/{id}/launch`. Ожидается `COLLECTING_REACTIONS`; другим видны только выбранные автором кандидаты. Для `NEAR` требуется отдельное `confirm_near_exception: true`.
4. `lena`, затем `maxim` отмечают **тот же** candidate как `WOULD_GO`. При достаточном числе реакций — `AWAITING_CONFIRMATION`, появляется `active_candidate_id`; до сборки `participants=[]`. Для варианта с `min_people=3` учитывается и предварительная реакция автора.
5. Каждый из `anton`, `lena`, `maxim` делает `POST /api/v1/dvizhi/{id}/confirm` с `{"candidate_id":"<active_candidate_id>"}`. После трёх подтверждений — `GATHERED`, `confirmed_count=3`, список `participants` содержит только подтвердивших. В Mini App это «ДВИЖ СОБРАЛСЯ». Если источник подтвердил отмену варианта перед подтверждением, API отвечает 409; откройте актуальное состояние вместо повторения старой кнопки.
6. Перед встречей scheduler перепроверяет источник и по сроку отправляет отдельное повторное подтверждение. Подтверждённый участник может ответить `POST /api/v1/dvizhi/{id}/reconfirm` или выйти через `/withdraw` с актуальным `candidate_id`. Отказ пересчитывает состав; если есть подходящий waitlist, следующий получает место. Без MAX credentials проверьте состояние через API и автоматические тесты, а не ожидайте реального push.

Для API-запросов используйте `Content-Type: application/json` и заголовок `X-Demo-User` соответствующего пользователя. Примеры тела и статусы — в [DATA-API.yaml](../DATA-API.yaml), полная схема — в [OpenAPI](openapi.json). Без заголовка пользователя локальный `/session` отвечает 401. `POST /api/v1/integrations/max/webhook` без корректного секрета отвечает 403; не отправляйте в него синтетический «реальный» MAX Update ради оценки интеграции.

## Реальный источник и MODEL-данные

Основной путь нового ДВИЖа использует реальные KudaGo/Geoapify данные. `NO_SOURCE` и `PROVIDER_UNAVAILABLE` — честные состояния; seed пользователей не создаёт кандидатов. В репозитории есть отдельный development endpoint `POST /api/v1/development/seed-demo/{group_id}`: он создаёт явно отмеченный `MODEL` объект для **старого** Offer/Plan-пути. Это не fallback нового ДВИЖа и не доказательство работы провайдера. В production endpoint закрыт.

## Зависимости и ограничения проверки

Каталог зависит от живых KudaGo и, для обычных мест/адресных подсказок, от серверного `GEOAPIFY_API_KEY`. Адресный поиск сначала предлагает выбранный город, затем допускает результаты других городов; сохраняемая точка всё равно принадлежит пользователю и городу компании. Без ключа Geoapify доступность мест ниже; при сетевой ошибке возможен `PROVIDER_UNAVAILABLE`. Неизвестная цена остаётся неизвестной. Локальный worker может создавать попытки доставки, но без production `MAX_BOT_TOKEN` реальную доставку MAX он не подтверждает. Для production проверки нужны согласованные публичные HTTPS URL, рабочий бот, подписка webhook и тестовые MAX-аккаунты — это `NEEDS_TEAM_INPUT`.

`backend/scripts/smoke_dvizh.py` автоматизирует путь с тремя **новыми** demo ID и живым KudaGo. Запускайте его только против отдельной одноразовой development БД/API: `DVIZH_SMOKE_URL=http://127.0.0.1:8001 python -m scripts.smoke_dvizh` из `backend/`. Он добавляет записи и не удаляет их. Регрессионные тесты детерминированны и не требуют живого провайдера.

## Остановка, сброс, troubleshooting

`docker compose down` останавливает стек и сохраняет БД; `docker compose up` возобновляет. `docker compose down -v` удаляет локальную PostgreSQL volume и все данные этого запуска. Если readiness не проходит, проверьте `docker compose ps` и логи `docker compose logs backend postgres`; если proxy не работает, проверьте `frontend` и адрес `/api/v1/health/ready` на порту frontend. Если в браузере другой пользователь, проверьте `?dev`-переключатель; MAX initData, когда оно есть, имеет приоритет над demo ID. Если нет вариантов, различайте `NO_SOURCE` и `PROVIDER_UNAVAILABLE`, смотрите город/занятие/окно и сетевую доступность провайдера. Временный сбой KudaGo может дать `PROVIDER_UNAVAILABLE` даже при работающем API: повторите проверку после восстановления источника, создав новый сигнал. Если ответы стабильно медленные, локально увеличьте `LEISURE_SEARCH_DEADLINE_SECONDS` и `KUDAGO_TIMEOUT_SECONDS` в `.env`, пересоздайте backend и повторите сценарий; это не гарантирует наличие данных у провайдера.
