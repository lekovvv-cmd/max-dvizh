# Чек-лист сдачи

## Repository — проверяется по коду и запуском

- [ ] README описывает продукт, запуск, компоненты, порты, окружение, данные, интеграции, ограничения и основной сценарий.
- [ ] Чистый clone запускается `docker compose up --build`; readiness API, frontend, `/api` proxy, worker и scheduler проходят smoke.
- [ ] `docs/openapi.json` совпадает с текущей схемой FastAPI; `DATA-API.yaml` проходит синтаксическую и ручную API-проверку.
- [ ] `.env.example` содержит только пустые секреты и явно локальные значения; `.env*` (кроме примера) не отслеживаются.
- [ ] `frontend/package-lock.json` и `backend/requirements.lock` присутствуют; Dockerfiles и `.dockerignore` присутствуют.
- [ ] Frontend/backend tests и GitHub Actions `frontend`, `backend`, `docker` зелёные на **финальном** SHA.
- [ ] Проверен состав зависимостей и применимые лицензии; нет закрытых API/библиотек без разрешения.
- [ ] Secret scan отслеживаемых файлов выполнен; обнаруженные реальные credentials удалены и заменены с ротацией.
- [ ] Локальный сценарий [EVALUATOR_SCENARIO.md](EVALUATOR_SCENARIO.md) пройден; синтетические данные не представлены как провайдерские.

## Команда заполняет перед отправкой — NEEDS_TEAM_INPUT

- [ ] Рабочая production-ссылка MAX Mini App: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.
- [ ] URL MAX-бота/username: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.
- [ ] Публичный HTTPS origin API для `DATA-API.yaml` (`base_url`) и webhook: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.
- [ ] Проверены MAX mobile и web: auth, запуск, webhook, review, match, gathered и deep link; результат/дата: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.
- [ ] Созданы тестовые MAX-аккаунты и компания с разрешённым доступом для проверяющих; детали переданы по официальному каналу.
- [ ] Рабочие `MAX_BOT_TOKEN`, `MAX_WEBHOOK_SECRET`, при необходимости `GEOAPIFY_API_KEY` и БД-credentials переданы **только** через установленный закрытый канал; в репозиторий/презентацию их не включать.
- [ ] Финальный commit SHA и ссылка на репозиторий закреплены: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.
- [ ] PDF-презентация и технический первый слайд подготовлены: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.
- [ ] Доказательства проблемы (интервью/опрос/наблюдения), если используются в защите, оформлены как реальные источники: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.
- [ ] Определены сегмент, город, владелец и следующий шаг пилота: `<TO_BE_FILLED_BEFORE_SUBMISSION>`.

Не отмечайте пункт исполненным по наличию кода без фактической проверки deployed MAX/HTTPS. Актуальные подробности — [README](../README.md), [презентация](PRESENTATION_CONTENT_CHECKLIST.md), [план пилота](PILOT_PLAN.md).
