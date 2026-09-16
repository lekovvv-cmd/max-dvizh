# MAX ДВИЖ

MAX Mini App + chatbot backend для компаний друзей 18–25: приватные условия превращаются в конкретные осуществимые планы, а не в подбор людей.

## Реализованный поток

`MAX entry → private group/invite → Signal or AutoSignal → KudaGo CandidatePlan → Exact/Near/Conflict → up to 3 private Offers → explicit choice → overlap invalidation → ConfirmedPlan → bot outbox → MAX share`.

Signal и AutoSignal содержат город, временное окно, категорию, бюджет, личную точку, радиус в км и размер группы. Координаты, бюджет, причины Near, отклонения и отказ никогда не возвращаются другим участникам. Near поддержан только для бюджета и требует отдельного подтверждения.

## Architecture

`React/Vite Mini App → FastAPI modular monolith → PostgreSQL`.

Backend verifies `WebApp.initData` server-side according to MAX HMAC rules, owns authorization/matching/locks, uses KudaGo only server-side, normalizes and snapshots provider results, and stores bot notifications in an outbox. `frontend/src/app/api.ts` is the typed API boundary. The pure functions in `backend/app/modules/matching/domain.py` perform Haversine, budget compatibility and interval overlap.

## Start

Prerequisite: Docker Desktop with Compose v2.

```powershell
docker compose up --build
```

Open `http://localhost:8080`; OpenAPI is at `http://localhost:8000/openapi.json`; readiness is at `http://localhost:8000/api/v1/health/ready`.

Local development accepts `X-Demo-User` only when `APP_ENV=development`. In MAX, the app sends `window.WebApp.initData`; production rejects any unvalidated identity.

## Environment and ports

Copy `.env.example` to `.env` for deployment values. Do not commit it. Runtime ports: frontend `8080`, backend `8000`, PostgreSQL `5432`.

`MAX_BOT_TOKEN` is required for a real MAX entry identity and Bot API notifications. `MAX_MINI_APP_URL` must be the public HTTPS Mini App URL registered for the bot. `MAX_BOT_USERNAME` is used to form public `startapp` links in deployment. KudaGo needs no secret.

## Verification walkthrough

1. Start Compose and create a company in the web Mini App.
2. In **Компания**, copy the invite token/link. In local QA use the explicitly labelled **Локальная проверка** control to switch to a second demo user, then open the invite link.
3. For each demo user, add a location from **Подать сигнал**, seed the explicitly labelled model data once, then submit a matching Signal. KudaGo is also queried and its events remain source-labelled.
4. Each member sees a private Offer. An Exact price can be accepted directly; for a 300→400 Near Offer the UI requires `Всё равно пойду` and only then counts the member.
5. Accepting an Offer invalidates that user's pending Offers that overlap its interval. When the minimum is reached, **ДВИЖ СОБРАЛСЯ** appears in Plans and can be shared through `WebApp.shareMaxContent`.
6. To exercise unavailable-provider recovery, block `kudago.com` after one successful sync; the backend serves the last snapshot when present and never labels it as live/demo data.

`DATA-API.yaml` contains reviewer API calls. `scripts/export-openapi.ps1` exports the generated contract. The full product/API/integration limitations are in `docs/08_API_AND_INTEGRATIONS.md` and `docs/18_RISKS_NON_GOALS.md`.

## Checks

```powershell
npm --prefix frontend ci
npm --prefix frontend run check
docker compose build
docker compose run --rm --no-deps backend ruff check .
docker compose run --rm --no-deps backend mypy app scripts
docker compose run --rm --no-deps backend pytest
./scripts/export-openapi.ps1
```

## Real MAX hand-off

The repository contains the live adapter and Bridge integration but cannot create a MAX bot, register the Mini App or run mobile/web QA without the owner's MAX Business account and bot token. Owner steps:

1. Create the bot and Mini App in MAX Business; set the deployed HTTPS URL.
2. Set `MAX_BOT_TOKEN`, `MAX_BOT_USERNAME`, `MAX_MINI_APP_URL` and a public HTTPS webhook subscription in deployment only.
3. Open the bot in MAX mobile and web; create a group through `startapp=<opaque invite token>`, complete the walkthrough, and verify the Bot API outbox notification plus in-MAX share.

## Limitations

- A MAX bot/account, HTTPS deployment and manual MAX mobile/web verification remain external-account work; no token is committed.
- KudaGo coverage and price quality vary by city. Missing price remains `Цена не указана`; model data is always labelled.
- The MVP has no booking, payments, travel-time estimates, chat reading, public feed, AI, or post-confirmation rescheduling engine.

Stop with `docker compose down`; `docker compose down -v` also deletes local PostgreSQL data.
