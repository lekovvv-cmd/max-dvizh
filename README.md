# MAX ДВИЖ

MAX Mini App + chatbot backend для компаний друзей 18–25: приватные условия превращаются в конкретные осуществимые планы, а не в подбор людей.

## Реализованный поток

`MAX entry → private group/invite → Signal or AutoSignal → KudaGo/Redis CandidatePlan → Exact/Near/Conflict → complete private cross-group Offer pool → explicit choice → overlap invalidation/recompute → ConfirmedPlan → independently dispatched bot outbox → MAX share`.

Signal и AutoSignal содержат город, временное окно, категорию, необязательные бюджет и радиус с личной точкой, а также размер группы. AutoSignal сохраняет browser IANA timezone и проверяет полный local interval. Финальный размер выбирается детерминированно и должен находиться в диапазоне каждого участника. Координаты, бюджет, причины Near, отклонения и отказ никогда не возвращаются другим участникам. Near поддержан только для бюджета и требует отдельного подтверждения.

## Architecture

`React/Vite Mini App → FastAPI modular monolith → PostgreSQL`, with Redis between KudaGo and matching for short-lived query-specific provider data.

Backend verifies `WebApp.initData` server-side according to MAX HMAC rules, owns authorization/matching/locks, uses KudaGo only server-side, cache-asides only the city/time/category DTO slice needed by an Intent, persists a source snapshot only after at least one Exact/Near eligible user creates a CandidatePlan, and stores bot notifications in an outbox. Missing facts for a user-set hard constraint are `UNVERIFIED`, not a hidden match or Conflict. `frontend/src/app/api.ts` is the typed API boundary. The pure functions in `backend/app/modules/matching/domain.py` perform Haversine, compatibility and interval overlap.

## Start

Prerequisite: Docker Desktop with Compose v2.

```powershell
docker compose up --build
```

Open `http://localhost:8080`; OpenAPI is at `http://localhost:8000/openapi.json`; readiness is at `http://localhost:8000/api/v1/health/ready`.

Local development accepts `X-Demo-User` only when `APP_ENV=development`. In MAX, the app sends `window.WebApp.initData`; production (`APP_ENV=production`) rejects any unvalidated identity.

## Environment and ports

Copy `.env.example` to `.env` for deployment values. Do not commit it. Runtime ports: frontend `8080`, backend `8000`, PostgreSQL `5432`.

`MAX_BOT_TOKEN` is required for a real MAX entry identity and Bot API notifications. `MAX_MINI_APP_URL` must be the public HTTPS Mini App URL registered for the bot. `MAX_BOT_USERNAME` is used to form public `startapp` links in deployment. `REDIS_URL` configures the provider cache. The Compose `worker` independently dispatches the PostgreSQL outbox and remains idle when the token is absent. KudaGo needs no secret.

## Verification walkthrough

1. Start Compose and create a company in the web Mini App.
2. In **Компания**, copy the invite token/link. In local QA use the explicitly labelled **Локальная проверка** control to switch to a second demo user, then open the invite link.
3. For each demo user, add a location from **Подать сигнал**, seed the explicitly labelled model data once, then submit a matching Signal. KudaGo is also queried and its events remain source-labelled.
4. Each member sees a private Offer. An Exact price can be accepted directly; for a 300→400 Near Offer the UI requires `Всё равно пойду` and only then counts the member.
5. Accepting an Offer invalidates that user's pending Offers that overlap its interval. When the minimum is reached, **ДВИЖ СОБРАЛСЯ** appears in Plans and can be shared through `WebApp.shareMaxContent`.
6. To exercise unavailable-provider recovery, block `kudago.com` after one successful sync; the backend serves the still-valid Redis cache when present and otherwise returns an honest unavailable state. It never uses fake live data or a PostgreSQL provider catalogue.

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
- KudaGo coverage and price quality vary by city. Missing optional metadata is omitted from UI; an unknown price cannot satisfy a budget-constrained match. Model data is always labelled.
- The MVP has no booking, payments, travel-time estimates, chat reading, public feed, AI, or post-confirmation rescheduling engine.

Stop with `docker compose down`; `docker compose down -v` also deletes local PostgreSQL data.

## Development database reset after provider-cache refactor

Migration `20260916_0003` copies each existing CandidatePlan's source facts into `candidate_plan_source_snapshots` and removes the old provider catalogue tables. Migration `20260916_0004` makes budget/origin/radius and member distance nullable for optional constraints. For disposable local/demo data, reset explicitly with `docker compose down -v`, then run `docker compose up --build`; never use this procedure against a deployment database.
