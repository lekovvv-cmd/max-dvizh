# MAX ДВИЖ

Технический каркас M0 для MAX Mini App + bot, который помогает группе друзей превратить намерение провести досуг в конкретный осуществимый план. Полная продуктовая спецификация находится в [`docs/`](docs/01_PRODUCT.md); этот commit намеренно не реализует продуктовые сценарии.

## Статус

Bootstrap готов: React/TypeScript/Vite frontend, FastAPI backend, PostgreSQL, Alembic, Docker Compose, базовые проверки и минимальный health-shell. Signal, AutoSignal, matching, Offers, MAX и KudaGo интеграции запланированы для следующих milestones и здесь не эмулируются.

## Core user flow

Целевой flow определён в [`docs/04_USER_FLOWS.md`](docs/04_USER_FLOWS.md): MAX entry → group → Signal/AutoSignal → CandidatePlan → private Offers → explicit choice → ConfirmedPlan → return to MAX. На M0 доступен только технический health-shell.

## Architecture and components

Модульный монолит: `frontend` (React/Vite) → `backend` (FastAPI) → `postgres`. Предусмотрены backend-модули из [`docs/06_ARCHITECTURE.md`](docs/06_ARCHITECTURE.md), но их бизнес-логика пока не реализована. Frontend nginx проксирует `/api/` в backend.

## Quick start

Требование: Docker Desktop with Docker Compose v2+.

```bash
docker compose up --build
```

После старта откройте `http://localhost:8080`; API healthcheck доступен по `http://localhost:8000/api/v1/health`.

## Environment and ports

Скопируйте `.env.example` в `.env` только если нужны другие локальные значения. В репозитории нет рабочих секретов.

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_DB` | `max_dvizh` | Local database name |
| `POSTGRES_USER` | `max_dvizh` | Local database user |
| `POSTGRES_PASSWORD` | `local_development_only` | Local-only Docker password; replace for deployment |
| `POSTGRES_PORT` | `5432` | PostgreSQL host port |
| `BACKEND_PORT` | `8000` | FastAPI host port |
| `FRONTEND_PORT` | `8080` | Frontend host port |

## Dependencies

Frontend dependencies are fixed in `frontend/package-lock.json`; backend dependencies are fixed in `backend/requirements.lock`. The runtime images are pinned in the Dockerfiles and `compose.yaml`.

## Integrations and data handling

MAX, KudaGo and all product integrations are deliberately pending. Their boundaries and provenance policy are documented in [`docs/08_API_AND_INTEGRATIONS.md`](docs/08_API_AND_INTEGRATIONS.md) and [`docs/13_DATA_POLICY.md`](docs/13_DATA_POLICY.md). No test, demo or provider data is included in M0.

## Verification

```bash
npm --prefix frontend ci
npm --prefix frontend run check
docker compose build
docker compose run --rm --no-deps backend ruff check .
docker compose run --rm --no-deps backend mypy app scripts
docker compose run --rm --no-deps backend pytest
docker compose up --build -d
```

Then request `GET /api/v1/health` and load the frontend shell. Export OpenAPI to `docs/openapi.json` with `./scripts/export-openapi.ps1` on PowerShell.

## Expected behavior

The frontend reports whether the backend health endpoint is reachable. The backend exposes only technical health and generated OpenAPI endpoints; no product contracts are claimed yet. Alembic is run before the backend starts.

## Stop and restart

Stop containers with `docker compose down`. To remove the local database volume as well, run `docker compose down -v` (this deletes local database data). Restart with `docker compose up --build`.

## Known limitations

- No deployed HTTPS endpoint, MAX bot/Mini App, current MAX identity validation or MAX web/mobile QA.
- No product API, authentication, matching, provider adapter, cache, notifications or E2E product flow.
- `DATA-API.yaml` intentionally lists only the live technical health check until real API contracts exist.
- Presentation, test accounts and frozen submission hash are pending later milestones.

## Submission checklist

The full submission requirements remain tracked in [`CHECKLIST.md`](CHECKLIST.md) and [`docs/14_HACKATHON_SUBMISSION.md`](docs/14_HACKATHON_SUBMISSION.md). This README will be expanded as M1–M11 are completed.
