# Backend AGENTS.md

Read root `AGENTS.md` first, then domain/state/architecture/data/integration/security docs.

## Backend is source of truth for
- MAX identity validation;
- group membership/authz;
- private Intents;
- compatibility;
- CandidatePlan generation;
- Near deviations;
- Offer state;
- time-conflict locking;
- ConfirmedPlan state;
- provenance.

Never trust client-provided identity, compatibility, distance, price classification or plan state.

## Domain
Pure matching functions must not depend on HTTP, ORM or provider SDKs.

## Concurrency
Offer acceptance can invalidate/recompute other plans. Use database transactions/locking (User → CandidatePlan → Offer) so participant limits and overlapping confirmations cannot become inconsistent. Recompute existing plans from their source snapshots, never a new provider call.

## Privacy
API responses must minimize private data. Hidden fields in UI are not privacy.

## Providers
External leisure sources implement an adapter. KudaGo is initial. Do not leak provider DTOs into domain.

## OpenAPI
Export OpenAPI 3.0/3.1 and maintain `DATA-API.yaml` for hackathon verification.
