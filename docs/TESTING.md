# Проверка ДВИЖа

## Автоматические проверки

```powershell
npm --prefix frontend ci
npm --prefix frontend run format:check
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build

cd backend
python -m pip install -r requirements-dev.txt
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
python -m pytest -q
python -m alembic upgrade head
```

Полный `pytest` использует отдельный PostgreSQL через `TEST_DATABASE_URL` для интеграционных тестов. Без него можно выполнить `python -m pytest -q --ignore=tests/test_postgres_reliability.py`, но это не заменяет PostgreSQL/Compose gate.

```powershell
docker compose up --build -d
docker compose ps
docker compose exec backend python -m alembic current
docker compose exec backend python -m alembic check
Invoke-WebRequest http://localhost:8000/api/v1/health/ready
Invoke-WebRequest http://localhost:8080/
```

На машине, где `8080` уже обслуживает Open Server Panel, запускайте Compose с `FRONTEND_PORT=18080` и проверяйте `http://127.0.0.1:18080/`. Заголовок ответа должен быть `MAX ДВИЖ`, сервер — `nginx`.

## Браузерный прогон

На ширинах 320, 360, 390, 430 и 1280 проверить первую подсказку, создание компании, выбор направления/занятия (в том числе несколько и wildcard), форму сигнала, свайп и кнопки, завершение всех PASS, явный запуск, «Движи», компанию, длинный заголовок, `NEAR`, ошибку провайдера, отсутствие горизонтальной прокрутки и reduced motion. Если API мокнут, фиксировать это отдельно: такой прогон проверяет UI, но не внешний KudaGo/MAX.

Для доменного сквозного сценария создайте трёх демопользователей в одной компании. A подаёт сигнал на занятие, которое **фактически** возвращается KudaGo; до запуска у B/C нет обзора. A отмечает два места и запускает движ. B/C без собственных сигналов отмечают один общий вариант. Только после минимума soft-реакций появляется запрос подтверждения. A/B/C подтверждают, затем участники видны в собранном движе. Две компании в одном Signal Batch должны иметь разные Dvizh ID и независимые счётчики. При пустом источнике ожидается `NO_SOURCE`, а не искусственный клуб.

Для повторяемого прогона на **отдельной disposable PostgreSQL базе** запустите API в development с этой базой и выполните `DVIZH_SMOKE_URL=http://127.0.0.1:8001 python -m scripts.smoke_dvizh` из `backend`. Скрипт создаёт трёх уникальных демопользователей и компанию, получает живые квесты KudaGo, проверяет идемпотентность сигнала и скрытость раунда до запуска, собирает три soft-реакции и три финальных подтверждения. Он оставляет тестовые записи в выбранной базе. Живой KudaGo может быть временно недоступен; для основного regression gate используются детерминированные тесты.

25.09.2026 скрипт прошёл на отдельной PostgreSQL-базе: KudaGo дал 57 проверенных кандидатов, приватность до запуска и три финальных подтверждения прошли, итоговый статус — `GATHERED`.

Регрессия источника: детерминированные тесты проверяют исчезнувший слот события, закрытое место, KudaGo 404 и временный сбой; подтверждённая отмена до запуска не создаёт review, после match закрывает финальное подтверждение и отменяет pending-уведомления, после сборки сообщает подтвердившим. Старая MAX-кнопка и stale API-запрос с прежним `candidate_id` не подтверждают запасной вариант.

Для MAX production: зарегистрировать webhook, проверить GET `/subscriptions`, недействительный секрет (403), `bot_started`, повтор callback, ссылку на конкретный движ, worker outbox, финальное сообщение и открытие Mini App в MAX mobile/web. Без реального токена/публичного домена эти шаги остаются для проверки на deployment.
