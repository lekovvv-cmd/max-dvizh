# Product API и MAX

База API: `/api/v1`. Пользовательские endpoints требуют `X-MAX-Init-Data` с валидной подписью MAX. `X-Demo-User` разрешён только при одновременных `APP_ENV=development` и `ALLOW_DEMO_AUTH=true`. MAX webhook использует отдельный секретный заголовок и не принимает Mini App auth вместо него.

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET / POST | `/session`, `/session/onboarding-seen` | Текущий пользователь и отметка локального онбординга |
| GET / POST | `/groups`, `/groups/join/{token}` | Компании пользователя, создание и вступление по приглашению |
| GET | `/locations/suggest?q=...&city=...` | Подсказки Geoapify: сначала выбранный город, затем другие города РФ при наличии серверного ключа |
| GET | `/leisure/taxonomy` | Направления, занятия, доступные wildcard-направления |
| POST | `/signals` | Сигнал в 1–12 компаний одного города; `X-Request-ID` делает повтор безопасным |
| PUT / DELETE | `/signals/{batch_id}` | Изменить или отменить ещё не запущенный сигнал |
| GET | `/dvizhi` | Видимые пользователю движи всех компаний |
| GET | `/dvizhi/{id}` | Полное личное product state одного движа |
| POST | `/dvizhi/{id}/more` | Повторить поиск до запуска |
| POST | `/dvizhi/{id}/places/search` | Поиск места по названию через Geoapify (если задан ключ) и KudaGo до запуска; добавляет только проверенных кандидатов |
| PUT | `/dvizhi/{id}/candidates/{candidate_id}/reaction` | `WOULD_GO` либо `PASS`, для `NEAR` требуется `confirm_near_exception` |
| POST | `/dvizhi/{id}/launch` | Явно открыть обзор компании |
| POST | `/dvizhi/{id}/confirm` | Окончательное подтверждение активного варианта |
| POST | `/dvizhi/{id}/decline` | Отказ до окончательного подтверждения |
| POST | `/dvizhi/{id}/reconfirm` | Ответ «Я иду» на отдельный вопрос перед встречей; body содержит актуальный `candidate_id` |
| POST | `/dvizhi/{id}/withdraw` | «Не смогу» до начала; body содержит актуальный `candidate_id`, состав и waitlist пересчитываются |
| POST / PUT | `/recurring-signals[/{id}]` | Создать или изменить еженедельное правило |
| POST | `/recurring-signals/{id}/pause` | Приостановить правило; незапущенные раунды отменяются |
| POST | `/recurring-signals/{id}/resume` | Возобновить правило |
| DELETE | `/recurring-signals/{id}` | Мягкое удаление: статус `DELETED`, запись остаётся в БД |
| POST | `/integrations/max/webhook` | Подписанный входящий MAX Update |

`POST /signals` принимает `group_ids`, `activity_categories`, `available_from`, `available_to`, `min_people`, необязательные `max_people`, `budget_max`, `origin_location_id`, `radius_km`. Ответ содержит `signal_batch_id` и отдельный `dvizhi[]` для каждой компании. Реальный пересекающийся подтверждённый движ блокирует создание **до** поиска провайдера: HTTP 409 с `code: SCHEDULE_CONFLICT` и `detail`. Устаревший кандидат и закрытый выбор также возвращают стабильные `code: CANDIDATE_STALE` / `SELECTION_CLOSED`. Режимы `NO_SOURCE` и `PROVIDER_UNAVAILABLE` явны. У ответов сигналов и `/dvizhi` общая типизированная модель `DvizhOut`, у вложенных карточек — `DvizhCandidateOut`; поля и nullable-значения зафиксированы в [OpenAPI](openapi.json). `signal_batch_id` виден только инициатору и иначе равен `null`. `my_reaction`, `my_confirmation`, `my_reconfirmed`, `my_reconfirm_available` личные; до `GATHERED` `participants=[]`.

Scheduler создаёт регулярные раунды, один раз напоминает об отсутствии review/подтверждения, сообщает автору о несобранном движе или отсутствии источника, перед встречей проверяет источник и задаёт подтверждённым отдельный вопрос с не более чем одним напоминанием. При `withdraw` следующий подходящий участник waitlist продвигается и получает уведомление. Все push проходят через PostgreSQL outbox: worker проверяет актуальность, отправляет и повторяет временные сбои; ссылки ведут в конкретный ДВИЖ.

Полный контракт текущего FastAPI экспортирован в [OpenAPI](openapi.json). Проверочный сценарий с динамическими ID и заранее созданными demo-ролями — в [EVALUATOR_SCENARIO.md](EVALUATOR_SCENARIO.md), набор — [test-data.json](test-data.json). Публичный HTTPS origin для `DATA-API.yaml` ещё не предоставлен командой, поэтому `base_url: null`.

## MAX Webhook

Секрет из `MAX_WEBHOOK_SECRET` сравнивается с `X-Max-Bot-Api-Secret`. Подписка включает `bot_started`, `message_callback`, `bot_removed`. Обработчик записывает отпечаток Update и outbox в PostgreSQL; повтор безопасен. `bot_started` отправляет одно приветствие с кнопкой открытия. Callback `confirm:<dvizh_id>` применяет доменную проверку участия и отвечает через `/answers`; устаревшее нажатие получает безопасный ответ. Обзорное уведомление одно на участника/движ, далее уведомления о match и сборе. Кнопка-ссылка открывает конкретный `startapp=dvizh_<id>`.

Команда подписки:

```sh
cd backend
python -m app.modules.max_integration.subscribe_webhook
```

Нужны `MAX_BOT_TOKEN`, `MAX_WEBHOOK_URL=https://<api-domain>/api/v1/integrations/max/webhook`, `MAX_WEBHOOK_SECRET` (5–256 букв/цифр/`_`/`-`), `MAX_BOT_USERNAME`. Подписка проверяется через `GET /subscriptions`. Используется домен `platform-api2.max.ru`; токен передаётся в `Authorization`, никогда в URL. Production требует доверенный HTTPS-сертификат и порт 443. После смены домена или секрета команду запускают повторно.

Официальные контракты: [Webhook](https://dev.max.ru/docs-api/methods/POST/subscriptions), [Update](https://dev.max.ru/docs-api/objects/Update), [callback answer](https://dev.max.ru/docs-api/methods/POST/answers), [KudaGo API](https://docs.kudago.com/api/).
