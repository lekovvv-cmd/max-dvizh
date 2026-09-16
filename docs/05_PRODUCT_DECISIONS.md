# 05 — Product decisions / ADR log

Do not reverse without explicit team approval.

## ADR-001 — Match plans, not people
Accepted. “Three people are free” is not a plan.

## ADR-002 — No separate Blind Consensus
Accepted. CandidatePlan/Offer is already concrete; Offer choice is the vote.

## ADR-003 — Multiple overlapping Offers are user-selected
Superseded by ADR-014 and ADR-015. Never choose socially for user.

## ADR-004 — Near exists
Accepted. MVP Near = budget. Always explicit acceptance.

## ADR-005 — Distance, not travel time
Accepted. Kilometers from user-selected origin; no minute estimate in MVP.

## ADR-006 — AutoSignals persist
Accepted. “Fridays / sauna / exactly 5” should not require daily check-in. Trigger ≠ attendance.

## ADR-007 — Multi-city MVP
Accepted. Not Kazan-only. Pilot geography separate.

## ADR-008 — No AI
Accepted. Not needed; adds risk and violates scope discipline.

## ADR-009 — KudaGo initial provider
Accepted for initial implementation behind provider adapter.

## ADR-010 — Backend privacy
Accepted. Do not send private raw data to other clients.

## ADR-011 — Modular monolith
Accepted. No microservices for hackathon MVP.

## ADR-012 — FastAPI + React/Vite + PostgreSQL
Accepted default unless real blocker appears.

## ADR-013 — CandidatePlan must be concrete
Accepted. “Я в деле” must have clear what/when/where/price status/own distance/participant requirement.

## ADR-014 — Unlimited Offer pool
Accepted. Product logic never caps the number of current pending Offers. Ranking and pagination may improve navigation but must not discard a compatible Offer.

## ADR-015 — Offer pool is cross-group
Accepted. `GET /offers` is global to the current user and every Offer exposes safe group ID and name.

## ADR-016 — Redis is the provider catalogue cache
Accepted. KudaGo query responses/normalized DTOs use parameterized Redis keys and TTL; PostgreSQL is not a cache fallback.

## ADR-017 — Persist source snapshot only for CandidatePlan
Accepted. One stable provider-item snapshot is saved only when a concrete CandidatePlan is created.

## ADR-018 — Omit missing optional UI metadata
Accepted. UI omits unavailable optional rows rather than printing “unknown”.

## ADR-019 — Unknown hard-constraint data is incompatible
Accepted. If an intent sets budget/radius and the provider lacks the data necessary to validate it, the item is Conflict for that intent.
