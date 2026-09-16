# AGENTS.md — MAX ДВИЖ

## Mission

Build **MAX ДВИЖ** as a production-quality hackathon MVP that can be verified end-to-end inside MAX.

Before implementation or architecture changes read:

1. `docs/00_CASE_REQUIREMENTS.md`
2. `docs/01_PRODUCT.md`
3. `docs/02_DOMAIN.md`
4. `docs/03_STATE_MACHINE.md`
5. `docs/04_USER_FLOWS.md`
6. `docs/05_PRODUCT_DECISIONS.md`
7. `docs/06_ARCHITECTURE.md`
8. `docs/10_ACCEPTANCE_CRITERIA.md`
9. `docs/14_HACKATHON_SUBMISSION.md`

## Source of truth

Do not silently reinterpret the product. If code and docs disagree, reconcile them. If ambiguous, prefer explicit ADRs in `docs/05_PRODUCT_DECISIONS.md`; otherwise choose the smallest implementation consistent with `docs/01_PRODUCT.md`.

## Product invariants

- ДВИЖ matches **concrete feasible plans**, not people with people.
- Intent is either one-time Signal or recurring AutoSignal.
- CandidatePlan is not a confirmed meeting.
- Offer is a private invitation to a concrete CandidatePlan.
- A user sees the full current pool of personally addressed pending Offers across all groups and chooses themselves.
- Never automatically choose between overlapping Offers.
- There is **no separate Blind Consensus voting stage**.
- Offer selection is the choice mechanism.
- Near never means accepted; Near requires explicit confirmation.
- Compatibility: Exact / Near / Conflict.
- Online MVP MUST support Near for budget.
- Distance is individual from each user's selected origin point.
- MVP uses kilometers, not travel-time estimates.
- AutoSignal means “invite me when conditions match”, not automatic attendance.
- MVP is multi-city where provider data is sufficient; do not hard-limit to Kazan.
- Product geography and pilot geography are separate.
- No AI/LLM features unless the team explicitly changes the spec.

## Privacy invariants

Never expose another user's:
- exact origin coordinates/address;
- private Intent/AutoSignal;
- exact personal budget;
- reason for incompatibility/Near;
- rejection;
- private recurring rule.

Backend is the source of truth. Do not send private raw data to clients merely to hide it in UI.

## Hackathon invariants

- Core flow MUST be verifiable in MAX.
- Solution includes a chatbot; Mini App is connected to the chatbot and is not an isolated service.
- Core functionality MUST work in MAX mobile and MAX web.
- Never commit working tokens, passwords, API keys or other secrets.
- Demo/model data must be explicitly marked.
- Use only dependencies/code with suitable licenses.
- Repository must be reproducible through Docker.

## Technical direction

Default:
- frontend: React + TypeScript + Vite;
- backend: FastAPI + Python;
- database: PostgreSQL;
- architecture: modular monolith;
- initial real leisure provider: KudaGo behind an adapter;
- bot/MAX integration owned by backend modules;
- external provider calls only from backend;
- Redis cache for temporary external provider data; persisted source snapshots only for CandidatePlans.

Do NOT add without an explicit need:
- microservices;
- Kafka/RabbitMQ;
- Kubernetes;
- CQRS/event sourcing;
- separate Redis cluster;
- AI services.

## MAX integration

MAX documentation changes. Before MAX-specific implementation, consult current official MAX docs. Do not rely only on old examples. Record final verified behavior in `docs/08_API_AND_INTEGRATIONS.md`.

## Development rules

- Inspect existing code before editing.
- Build vertical slices, not disconnected mock UI.
- Domain matching logic must be deterministic and unit-testable.
- Keep HTTP/ORM/provider schemas outside pure domain functions.
- Use transactions/locking where concurrent Offer acceptance can violate constraints.
- Do not add out-of-scope features “because useful”.
- Update docs when behavior changes.
- Add regression tests for fixed bugs.

## Required UI states

Every core async surface needs loading, success, empty, error, and expired/stale states where relevant, with a recovery path.

## Verification before completion

Run available:
- formatter;
- lint;
- typecheck;
- backend tests;
- frontend tests;
- integration tests;
- E2E for core flows;
- production frontend build;
- Docker build/start smoke.

Docker build must remain comfortably within the case's 5-minute build constraint excluding initial base-image downloads.

## Definition of done

A feature is done only when:
1. backend/domain behavior exists;
2. UI is connected to real behavior;
3. MAX/external integration is real where claimed;
4. loading/error/empty states work;
5. privacy/security invariants hold;
6. tests cover success and meaningful failures;
7. docs match implementation;
8. flow is manually verifiable.

## Final MVP vertical slice

MAX entry
→ group/company
→ Signal or AutoSignal
→ CandidatePlan generation
→ Exact/Near/Conflict
→ full private Offer pool
→ explicit user choice
→ overlapping-plan recomputation
→ enough accepted users
→ ConfirmedPlan
→ bot notification/share back into MAX.

Do not stop at scaffolding, mocked UI, or partial CRUD.
