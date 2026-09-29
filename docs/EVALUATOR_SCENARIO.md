# Сценарий проверки MAX ДВИЖ

## Предусловия и запуск

Из корня чистого clone запустите `docker compose up --build`. Локальный Compose включает `APP_ENV=development` и `ALLOW_DEMO_AUTH=true`; MAX-токен не нужен. Дождитесь `GET http://localhost:8000/api/v1/health/ready` → `{"status":"ready","database":"ok"}`. Откройте `http://localhost:8080` и `http://localhost:8080/api/v1/health/ready`: второй адрес проверяет nginx → backend. Swagger: `http://localhost:8000/docs`.

Если 8080 занят, перед запуском задайте `FRONTEND_PORT=18080` и используйте `http://localhost:18080`. Состояние контейнеров: `docker compose ps`; нужны `postgres`, `backend`, `worker`, `scheduler`, `frontend`.

## Demo-пользователи и компания

Локальные ID: `anton` (инициатор), `lena` и `maxim` (участники). Это не аккаунты MAX и у них нет паролей. В браузере по умолчанию открыт `anton`; в «Компании» по URL `http://localhost:8080/?dev` доступен переключатель ID. После смены перезагружается страница. API принимает заголовок `X-Demo-User: anton|lena|maxim` только в development. Пользователи создаются при первом запросе `GET /api/v1/session`.

Под `anton` создайте компанию в поддерживаемом городе и сохраните приглашение. Переключитесь на `lena` в «Компании» с `?dev`: после перезагрузки у неё ещё нет компании и переключатель не показывается, поэтому откройте сохранённую ссылку-приглашение. У вступившей `lena` снова доступна «Компания»; через неё переключитесь на `maxim` и откройте то же приглашение. Теперь можно возвращаться к `anton` через переключатель. Тот же путь через API: `POST /api/v1/groups` с `{"name":"Demo company","city_slug":"msk"}` от `anton` возвращает динамические `id` и `invite_token`; `POST /api/v1/groups/join/{invite_token}` от каждого другого demo ID. ID не фиксированы и не входят в репозиторий. Не используйте production БД для этой проверки.

## Основной сценарий и ожидаемые состояния

1. Под `anton` выберите компанию, занятие из `GET /api/v1/leisure/taxonomy`, будущее окно и минимум 3 участников. `POST /api/v1/signals` принимает `group_ids`, `activity_categories`, `available_from`, `available_to`, `min_people`; желательно передать уникальный `X-Request-ID`. Ответ содержит `signal_batch_id` и `dvizhi[]` с новыми ID. Для одного запроса к нескольким компаниям создаются независимые движи.
2. Если доступны реальные записи провайдера, `dvizhi[0].status=CHOOSING_CANDIDATES`, `candidates[]` содержит провайдера и доступные факты источника. Если записей нет — `NO_SOURCE`; при временном сбое — `PROVIDER_UNAVAILABLE`. Смените занятие/город/окно или повторите поиск после восстановления источника. Эти состояния не следует подменять demo-объектами.
3. До запуска `GET /api/v1/dvizhi/{id}` от `lena`/`maxim` возвращает 404. `anton` отмечает один подходящий `candidate_id` через `PUT /api/v1/dvizhi/{id}/candidates/{candidate_id}/reaction` с `{"value":"WOULD_GO"}` и делает `POST /api/v1/dvizhi/{id}/launch`. Ожидается `COLLECTING_REACTIONS`; другим видны только выбранные автором кандидаты. Для `NEAR` требуется отдельное `confirm_near_exception: true`.
4. `lena`, затем `maxim` отмечают **тот же** candidate как `WOULD_GO`. При достаточном числе реакций — `AWAITING_CONFIRMATION`, появляется `active_candidate_id`; до сборки `participants=[]`. Для варианта с `min_people=3` учитывается и предварительная реакция автора.
5. Каждый из `anton`, `lena`, `maxim` делает `POST /api/v1/dvizhi/{id}/confirm` с `{"candidate_id":"<active_candidate_id>"}`. После трёх подтверждений — `GATHERED`, `confirmed_count=3`, список `participants` содержит только подтвердивших. В Mini App это «ДВИЖ СОБРАЛСЯ». Если источник подтвердил отмену варианта перед подтверждением, API отвечает 409; откройте актуальное состояние вместо повторения старой кнопки.

Для API-запросов используйте `Content-Type: application/json` и заголовок `X-Demo-User` соответствующего пользователя. Примеры тела и статусы — в [DATA-API.yaml](../DATA-API.yaml), полная схема — в [OpenAPI](openapi.json). Без заголовка пользователя локальный `/session` отвечает 401. `POST /api/v1/integrations/max/webhook` без корректного секрета отвечает 403; не отправляйте в него синтетический «реальный» MAX Update ради оценки интеграции.

## Зависимости и ограничения проверки

Каталог зависит от живых KudaGo и, для обычных мест/адресных подсказок, от серверного `GEOAPIFY_API_KEY`. Без ключа Geoapify доступность мест ниже; при сетевой ошибке возможен `PROVIDER_UNAVAILABLE`. Неизвестная цена остаётся неизвестной. Локальный worker может создавать попытки доставки, но без production `MAX_BOT_TOKEN` реальную доставку MAX он не подтверждает. Для production проверки нужны согласованные публичные HTTPS URL, рабочий бот, подписка webhook и тестовые MAX-аккаунты; всё это [NEEDS_TEAM_INPUT](SUBMISSION_CHECKLIST.md).

`backend/scripts/smoke_dvizh.py` автоматизирует путь с тремя **новыми** demo ID и живым KudaGo. Запускайте его только против отдельной одноразовой development БД/API: `DVIZH_SMOKE_URL=http://127.0.0.1:8001 python -m scripts.smoke_dvizh` из `backend/`. Он добавляет записи и не удаляет их. Регрессионные тесты детерминированны и не требуют живого провайдера.

## Остановка, сброс, troubleshooting

`docker compose down` останавливает стек и сохраняет БД; `docker compose up` возобновляет. `docker compose down -v` удаляет локальную PostgreSQL volume и все данные этого запуска. Если readiness не проходит, проверьте `docker compose ps` и логи `docker compose logs backend postgres`; если proxy не работает, проверьте `frontend` и адрес `/api/v1/health/ready` на порту frontend. Если в браузере другой пользователь, проверьте `?dev`-переключатель; MAX initData, когда оно есть, имеет приоритет над demo ID. Если нет вариантов, различайте `NO_SOURCE` и `PROVIDER_UNAVAILABLE`, смотрите город/занятие/окно и сетевую доступность провайдера.
