# 06 — Architecture

## Style
Modular monolith.

## Runtime
```text
MAX
├─ Chatbot
└─ Mini App
     ↓
React + TS + Vite
     ↓ HTTPS
FastAPI backend
├─ MAX integration
├─ auth/users/groups
├─ locations/intents
├─ matching/plans/offers
├─ leisure provider adapters
├─ provenance/cache
├─ notifications/share + same-image outbox worker
└─ same-image AutoSignal scheduler (30-minute poll, PostgreSQL advisory lock)
     ↓
PostgreSQL ← CandidatePlans, snapshots and domain entities
     ↑
matching engine ← Redis (parameterized TTL cache) ← KudaGo public API
```

The scheduler subtracts evaluation duration from the next poll delay, so the configured 30-minute interval is measured between run starts when a run completes within that interval. A second instance skips a run while the PostgreSQL advisory lock is held.

## Suggested repo after bootstrap
```text
/
├─ AGENTS.md
├─ README.md
├─ compose.yaml
├─ .env.example
├─ docs/
├─ frontend/
│  └─ AGENTS.md
├─ backend/
│  └─ AGENTS.md
├─ tests/e2e/
└─ scripts/
```

## Backend modules
`auth`, `users`, `groups`, `locations`, `intents`, `leisure`, `matching`, `plans`, `offers`, `max_integration`, `data_provenance`, `common`.

## Lightweight layering
API/router → application service → domain logic → repository/provider.

## Matching engine
Pure normalized inputs, no HTTP/SQL/KudaGo DTOs. Returns compatibility, time containment and participant-range feasibility. One eligible member can create a concrete CandidatePlan and receive an Offer before the confirmation minimum is met. The application service sends Offers to all eligible users and manages confirmed-open capacity and private waitlist. Every regeneration entry point locks the Company row in PostgreSQL, serializing plan lookup/creation across scheduler and HTTP-triggered work.

## Participant size
Target group 4–12. Effective capacity uses current Company membership unless accepted participants specify a lower explicit maximum. No advance social cohort is selected.

## Distance
Haversine/geodesic from user's origin to venue/event coords.

## Cache and provider data
Redis holds short-lived normalized KudaGo Event and Place responses through cache-aside under actual query keys such as `kudago:items:{city}:{start-unix}-{end-unix}:{categories-hash}`. The adapter requests only the Intent's city/time/category slice; a cache hit avoids KudaGo, while a miss fetches and stores that same slice. PostgreSQL never mirrors the provider catalogue: a CandidatePlan alone gets a durable provider-item snapshot.

## Bot
Prefer backend-owned bot integration; no separate bot microservice unless needed.

## Reliability worker

Compose runs a small `worker` process from the backend image. It claims PostgreSQL outbox rows with `FOR UPDATE SKIP LOCKED`, marks them PROCESSING before calling MAX, and retries transient failures with bounded backoff. It stays idle when no bot token is configured; no Celery, broker, or extra service is introduced.

## API
Own backend API → expose/export OpenAPI and maintain DATA-API.yaml.

## Docker
Local: frontend, backend, worker, scheduler, PostgreSQL and Redis. Target `docker compose up --build`. Build <=5 minutes excluding initial base image downloads.
