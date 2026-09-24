# Product API и MAX

База API: `/api/v1`. Пользовательские endpoints требуют `X-MAX-Init-Data` с валидной подписью MAX. В `APP_ENV=development` разрешён `X-Demo-User`. MAX webhook использует отдельный секретный заголовок и не принимает Mini App auth вместо него.

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/leisure/taxonomy` | Направления, занятия, доступные wildcard-направления |
| POST | `/signals` | Сигнал в 1–12 компаний одного города; `X-Request-ID` делает повтор безопасным |
| PUT / DELETE | `/signals/{batch_id}` | Изменить или отменить ещё не запущенный сигнал |
| GET | `/dvizhi` | Видимые пользователю движи всех компаний |
| GET | `/dvizhi/{id}` | Полное личное product state одного движа |
| POST | `/dvizhi/{id}/more` | Повторить поиск до запуска |
| POST | `/dvizhi/{id}/places/search` | Поиск места по названию в KudaGo до запуска; добавляет только проверенных кандидатов |
| PUT | `/dvizhi/{id}/candidates/{candidate_id}/reaction` | `WOULD_GO` либо `PASS`, для `NEAR` требуется `confirm_near_exception` |
| POST | `/dvizhi/{id}/launch` | Явно открыть обзор компании |
| POST | `/dvizhi/{id}/confirm` | Окончательное подтверждение активного варианта |
| POST | `/dvizhi/{id}/decline` | Отказ до окончательного подтверждения |
| POST / PUT / DELETE | `/recurring-signals[/{id}]` | Создать, изменить, отключить еженедельное правило |
| POST | `/integrations/max/webhook` | Подписанный входящий MAX Update |

`POST /signals` принимает `group_ids`, `activity_categories`, `available_from`, `available_to`, `min_people`, необязательные `max_people`, `budget_max`, `origin_location_id`, `radius_km`. Ответ содержит `signal_batch_id` и отдельный `dvizhi[]` для каждой компании. Режимы `NO_SOURCE` и `PROVIDER_UNAVAILABLE` явны. В `GET /dvizhi` поля `my_reaction`, `my_confirmation` личные; до `GATHERED` `participants=[]`.

## MAX Webhook

Секрет из `MAX_WEBHOOK_SECRET` сравнивается с `X-Max-Bot-Api-Secret`. Подписка включает `bot_started`, `message_callback`, `bot_removed`. Обработчик записывает отпечаток Update и outbox в PostgreSQL; повтор безопасен. `bot_started` отправляет одно приветствие с кнопкой открытия. Callback `confirm:<dvizh_id>` применяет доменную проверку участия и отвечает через `/answers`; устаревшее нажатие получает безопасный ответ. Обзорное уведомление одно на участника/движ, далее уведомления о match и сборе. Кнопка-ссылка открывает конкретный `startapp=dvizh_<id>`.

Команда подписки:

```sh
cd backend
python -m app.modules.max_integration.subscribe_webhook
```

Нужны `MAX_BOT_TOKEN`, `MAX_WEBHOOK_URL=https://<api-domain>/api/v1/integrations/max/webhook`, `MAX_WEBHOOK_SECRET` (5–256 букв/цифр/`_`/`-`), `MAX_BOT_USERNAME`. Подписка проверяется через `GET /subscriptions`. Используется домен `platform-api2.max.ru`; токен передаётся в `Authorization`, никогда в URL. Production требует доверенный HTTPS-сертификат и порт 443. После смены домена или секрета команду запускают повторно.

Официальные контракты: [Webhook](https://dev.max.ru/docs-api/methods/POST/subscriptions), [Update](https://dev.max.ru/docs-api/objects/Update), [callback answer](https://dev.max.ru/docs-api/methods/POST/answers), [KudaGo API](https://docs.kudago.com/api/).
