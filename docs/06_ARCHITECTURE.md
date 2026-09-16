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
└─ notifications/share
     ↓
PostgreSQL
     ↓
KudaGo public API
```

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
Pure normalized inputs, no HTTP/SQL/KudaGo DTOs. Returns compatibility, feasible subsets, deviations, ranking data.

## Candidate subset
Target group 4–12. Bounded subset enumeration is acceptable if measured/tested. Do not add solver before simple deterministic logic proves insufficient.

## Distance
Haversine/geodesic from user's origin to venue/event coords.

## Cache
Persist last successful normalized provider data + timestamp. Redis not required; PostgreSQL snapshot/cache is fine.

## Bot
Prefer backend-owned bot integration; no separate bot microservice unless needed.

## API
Own backend API → expose/export OpenAPI and maintain DATA-API.yaml.

## Docker
Local: frontend, backend, postgres. Target `docker compose up --build`. Build <=5 minutes excluding initial base image downloads.
