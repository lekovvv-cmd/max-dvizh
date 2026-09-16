# Prompt 02 — Implement MAX ДВИЖ MVP end-to-end

Ты находишься в подготовленном репозитории MAX ДВИЖ. Не полагайся на память прошлого чата.

Сначала прочитай root `AGENTS.md`, все требуемые им docs, `CHECKLIST.md`, `frontend/AGENTS.md`, `backend/AGENTS.md`. Это источник истины.

## Goal
Полностью реализуй online-stage MVP end-to-end:

MAX entry
→ group
→ Signal/AutoSignal
→ CandidatePlan generation
→ Exact/Near/Conflict
→ complete private Offer pool across a user's groups
→ explicit user choice
→ overlap recomputation
→ ConfirmedPlan
→ bot notification
→ final return/share in MAX.

Не останавливайся на scaffolding/UI mock/CRUD/fake integration/partial happy path.

## Order
Следуй `docs/16_IMPLEMENTATION_PLAN.md`, вертикальными slices. После milestone запускай тесты и оставляй repo в рабочем состоянии.

## MAX
До MAX-specific кода проверь текущую официальную документацию. Не придумывай API methods.

Если нужен внешний token/account action, которого у тебя нет:
- реализуй code/config/adapter вокруг него;
- оставь точную инструкцию владельцу;
- продолжи остальные задачи;
- не подменяй интеграцию фейковой и не называй её готовой.

## External data
Интегрируй реальный KudaGo provider через backend adapter: normalization, provenance, timeout, cache, last-snapshot fallback, multi-city. Frontend не вызывает provider напрямую.

## Product constraints
Не нарушай:
- no Blind Consensus;
- no auto-choice between overlapping Offers;
- Near requires explicit confirmation;
- individual km from origin, no travel-time claim;
- AutoSignal != attendance;
- no Kazan-only hardcode;
- backend privacy;
- no AI.

## Quality
Implement migrations, typed frontend API, loading/error/empty states, authz/security, transaction-safe Offer acceptance, unit/integration/E2E from test plan, responsive MAX mobile/web UI.

## Submission readiness
Prepare complete README, Docker one-command, `.env.example`, OpenAPI export, `DATA-API.yaml`, test-data instructions, known limitations, exact verification walkthrough and checklist status. Verify Docker build time target.

## Finish criteria
Do not call complete until all possible MUST acceptance criteria pass, core E2E passes repeatedly, production build succeeds, Docker starts cleanly, no secrets are committed, docs match behavior.

For criteria blocked only by missing credentials/account action, state exactly what is implemented, what external action remains and how to verify once supplied.

At the end report completed features, test results, real MAX verification status, limitations, checklist gaps and exact run commands.
