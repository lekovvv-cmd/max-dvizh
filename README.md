# MAX ДВИЖ

MAX Mini App + chatbot backend для компаний друзей 18–25: приватные условия превращаются в конкретные осуществимые планы, а не в подбор людей.

## Реализованный поток

`MAX entry → private group/invite → Signal or AutoSignal → KudaGo/Redis CandidatePlan → Exact/Near/Conflict → complete private cross-group Offer pool → explicit choice → overlap invalidation/recompute → ConfirmedPlan → independently dispatched bot outbox → MAX share`.

Город принадлежит Company. Одностраничный Signal может охватывать несколько компаний одного города и несколько категорий; его условия необязательны. «Неважно» для размера означает минимум двое и отсутствие личного верхнего предела. AutoSignal сохраняет IANA timezone, проверяет полный local interval и обрабатывается отдельным периодическим scheduler. Все совместимые участники получают Offer. План подтверждается при выполнимом составе и остаётся открытым до верхнего предела; новый участник с более строгим минимумом ждёт выполнения личного условия, не отменяя уже подтверждённый состав. Для «Ровно N» действует очередь по времени ответа. Координаты, бюджет, причины Near, отклонения и отказ никогда не возвращаются другим участникам. Near поддержан только для бюджета и требует отдельного подтверждения.

## Architecture

`React/Vite Mini App → FastAPI modular monolith → PostgreSQL`, with Redis between KudaGo and matching for short-lived query-specific provider data.

Backend verifies `WebApp.initData` server-side according to MAX HMAC rules, owns authorization/matching/locks, uses KudaGo Events and Places only server-side, cache-asides city/time/category provider slices, persists a source snapshot only for a CandidatePlan, and stores bot notifications in an outbox. A second backend service polls AutoSignals. Missing facts for a user-set hard constraint are `UNVERIFIED`, not an Offer. Place opening hours remain explicitly unverified when KudaGo cannot establish a specific slot. `frontend/src/app/api.ts` is the typed API boundary. The pure functions in `backend/app/modules/matching/domain.py` perform Haversine, compatibility and interval overlap.

## Start

Prerequisite: Docker Desktop with Compose v2.

```powershell
docker compose up --build
```

Open `http://localhost:8080`; OpenAPI is at `http://localhost:8000/openapi.json`; readiness is at `http://localhost:8000/api/v1/health/ready`.

Local development accepts `X-Demo-User` only when `APP_ENV=development`. In MAX, the app sends `window.WebApp.initData`; production (`APP_ENV=production`) rejects any unvalidated identity.

## Environment and ports

Copy `.env.example` to `.env` for deployment values. Do not commit it. Runtime ports: frontend `8080`, backend `8000`, PostgreSQL `5432`.

`MAX_BOT_TOKEN` is required for real MAX identity, chat-bound Company creation and Bot API notifications. `MAX_MINI_APP_URL` must be the public HTTPS Mini App URL registered for the bot. `MAX_BOT_USERNAME` forms public `startapp` links. `REDIS_URL` configures the provider cache. Compose runs an outbox `worker` and an AutoSignal `scheduler`. KudaGo needs no secret.

## Verification walkthrough

1. Start Compose and create a company in the web Mini App.
2. In **Компания**, copy the invite link. In local QA use the explicitly labelled **Локальная проверка** control to switch to a second demo user, then open the link. A chat-bound Company can also be created from a signed MAX chat launch.
3. Optionally save a real GPS point in **Компания**. Submit a Signal on one screen, optionally selecting multiple companies and categories. KudaGo Events and Places are queried. Model data, if seeded explicitly for QA, is labelled.
4. Each member sees a private Offer. An Exact price can be accepted directly; for a 300→400 Near Offer the UI requires `Всё равно пойду` and only then counts the member.
5. Accepting an Offer invalidates that user's pending Offers that overlap its interval. Before the minimum, **Собираем** is visible. At the minimum, the plan is confirmed and remains open for additional eligible participants until its effective maximum. Exact-N overflow joins a private waitlist. Users can cancel participation before cutoff; MAX sharing uses `WebApp.shareMaxContent`.
6. To exercise unavailable-provider recovery, block `kudago.com` after one successful sync; the backend serves the still-valid Redis cache when present and otherwise returns an honest unavailable state. It never uses fake live data or a PostgreSQL provider catalogue.

`DATA-API.yaml` contains reviewer API calls. `scripts/export-openapi.ps1` exports the generated contract. The full product/API/integration limitations are in `docs/08_API_AND_INTEGRATIONS.md` and `docs/18_RISKS_NON_GOALS.md`.

## Checks

```powershell
npm --prefix frontend ci
npm --prefix frontend run check
docker compose build
docker compose run --rm --no-deps backend ruff check .
docker compose run --rm --no-deps backend mypy app scripts
docker compose exec -T postgres psql -U max_dvizh -d postgres -c "CREATE DATABASE max_dvizh_test OWNER max_dvizh;" # once per local database
docker compose run --rm --no-deps -e TEST_DATABASE_URL=postgresql+psycopg://max_dvizh:local_development_only@postgres:5432/max_dvizh_test backend pytest
./scripts/export-openapi.ps1
```

The PostgreSQL reliability tests recreate tables in `TEST_DATABASE_URL`; use a dedicated test database. If `max_dvizh_test` already exists, skip its creation command. Replace the sample local credentials above when overriding Compose's PostgreSQL defaults. GitHub Actions also starts the full Compose stack and checks the backend readiness endpoint and Mini App HTTP response after the build.

## Real MAX hand-off

The repository contains the live adapter and Bridge integration but cannot create a MAX bot, register the Mini App or run mobile/web QA without the owner's MAX Business account and bot token. Owner steps:

1. Create the bot and Mini App in MAX Business; set the deployed HTTPS URL.
2. Set `MAX_BOT_TOKEN`, `MAX_BOT_USERNAME`, `MAX_MINI_APP_URL` and a public HTTPS webhook subscription in deployment only.
3. Open the bot in MAX mobile and web; create a group through `startapp=<opaque invite token>`, complete the walkthrough, and verify the Bot API outbox notification plus in-MAX share.

## Limitations

- A MAX bot/account, HTTPS deployment and manual MAX mobile/web verification remain external-account work; no token is committed.
- KudaGo coverage and price quality vary by city. Unknown prices cannot satisfy a budget-constrained match; FROM prices are shown as lower bounds. Place opening hours are marked unverified when a concrete slot cannot be established. Model data is always labelled.
- The MVP has no booking, payments, travel-time estimates, chat reading, public feed, AI, or post-confirmation rescheduling engine.

Stop with `docker compose down`; `docker compose down -v` also deletes local PostgreSQL data.

## Development database reset after provider-cache refactor

Migration `20260916_0003` copies each existing CandidatePlan's source facts into `candidate_plan_source_snapshots` and removes the old provider catalogue tables. Migration `20260916_0004` makes budget/origin/radius and member distance nullable for optional constraints. Revisions `20260918_0006` through `0010` add Signal batches, provider and invitation states, place metadata, Company timezone and a per-city saved-place default. CI checks both a fresh PostgreSQL upgrade to head and an upgrade from populated `20260916_0005`, including data preservation and category backfill. For disposable local/demo data, reset explicitly with `docker compose down -v`, then run `docker compose up --build`; never use this procedure against a deployment database.
