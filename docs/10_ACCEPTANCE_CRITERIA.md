# 10 — Acceptance criteria

## AC-001 Private Signal
Given Anton creates a Signal, another member cannot obtain Anton's active Signal, exact constraints, budget or origin through normal API responses.

## AC-002 AutoSignal does not auto-accept
Compatible CandidatePlan creates PENDING Offer; user is not accepted until explicit action.

## AC-003 Exact budget
budget_max=500, price=400 → budget Exact.

## AC-004 Near budget
budget_max=300, price=400 and delta within configured Near threshold → Near Offer, explicit +100 wording, not accepted until explicit exception confirmation.

## AC-005 Conflict budget
Plan exceeds Near threshold → Conflict, no normal Offer.

## AC-006 Individual distance
Different origins produce different distance_km; each user sees only own distance; other's exact origin is not exposed.

## AC-007 No travel-time claim
UI uses km and never claims minute travel estimate in MVP.

## AC-008 Exactly N
min=max=5 → ConfirmedPlan participant count exactly 5.

## AC-009 More compatible than max
7 compatible, exact max=5 → all seven receive Offers; first five responses take places, later responders privately waitlist.

## AC-010 Multiple overlapping Offers
Bowling + PC Club overlap; user may see both with any other pending offers in the unrestricted global pool; system does not choose automatically.

## AC-011 Accept overlap
Accept PC Club → selected Offer accepted, overlapping Bowling participation invalidated/recomputed, Bowling candidate recomputed.

## AC-012 Independent plans
No shared conflict → both may proceed.

## AC-013 Confirmation threshold
min=4; 3 accepts → not confirmed; fourth valid accept → confirmed if all constraints hold.

## AC-014 Near privacy
Before Andrey accepts +100 Near, others do not receive his exact budget or identity as Near cause.

## AC-015 Provider timeout
KudaGo timeout + valid cache → allowed cached data, visible freshness, flow remains usable.

## AC-016 Model data honesty
Demo/model item is explicitly marked and not represented as live provider data.

## AC-017 Unknown price
No reliable price → no invented number and no placeholder row in UI. With a user-set budget this is `UNVERIFIED` and gets no Offer; without budget it does not block matching.

## AC-026 Optional budget and radius
An Intent may omit budget and/or origin/radius. Missing price/coordinates are allowed for omitted constraints, while a set budget/radius with missing provider facts yields Unverified, not Conflict.

## AC-027 CandidatePlan eligibility gate
An item with only Conflict/Unverified users creates neither CandidatePlan nor source snapshot; one Exact/Near eligible user creates both.

## AC-025 Unrestricted cross-group Offer pool
Five valid pending Offers from multiple groups, including Exact and Near, are all returned by `GET /offers`, each with safe `group_id` and `group_name`; ranking never discards one.

## AC-018 MAX core flow
Judge can enter via MAX, open Mini App, join/create context, create/activate Intent, receive Offer, accept, reach ConfirmedPlan, return/share result in MAX.

## AC-019 Mobile/web
Core scenario works in MAX mobile and MAX web.

## AC-020 Docker
Fresh environment can start documented local components with one Docker Compose command.

## AC-021 No secrets
Repository scan has no working token/password/API key committed.

## AC-022 OpenAPI
Backend OpenAPI exists/exportable and matches mandatory endpoints in DATA-API.yaml.

## AC-023 Recovery
Temporary provider/backend error has retry/recovery without mandatory full reset where reasonable.

## AC-024 Multi-city
No domain rule hardcodes Kazan-only. Cities derive from provider/config/data policy.

## AC-028 Reliability correctness
Exactly-N users are never confirmed below N; fixed events fit full one-time availability; AutoSignal evaluates weekday/time/timezone; and a real KudaGo end timestamp is not extended.

## AC-029 Atomic choice and recovery
Concurrent accepts cannot exceed effective capacity or accept overlapping Offers for one user. Exact-N overflow is privately waitlisted in response order. Reject/invalidation/cancellation recomputes from the persisted source snapshot without re-offering a rejected user.

## AC-030 Confirmed but open
Eight compatible members with min=3 all receive Offers. Three valid responses confirm the plan; the remaining five can join until Company capacity or cutoff.

## AC-031 Signal batch and saved places
Multi-company Signal creation/edit/cancel is atomic and rejects mixed cities. No saved place is required for a Signal; a radius requires a real user-owned location in the Company city. No fake coordinates are generated.

## AC-032 AutoSignal periodic matching
Active recurring rules are evaluated immediately at create/edit/resume and at least every 30 minutes over seven days, with idempotent plan/Offer/outbox creation under concurrent scheduler instances.

## AC-033 Provider facts
KudaGo Events and Places are normalized separately. Every verified Event occurrence has a distinct CandidatePlan identity; missing Event end blocks normal Offers. Place slots fit complete availability and visibly warn when opening hours cannot be verified. FROM price remains a floor with explicit uncertainty.

## AC-034 Empty-source and invitation states
An active Signal distinguishes provider outage, empty provider result and no feasible plan; its owner can retry the saved query. A missing invite token yields an invalid state, while an explicitly expired known token yields a distinct expired state. The initial join result remains visible even before the user has a Company.

## AC-035 Confirmed core with stricter responder
A and B accept with min=2 and confirm an open plan. C responds with min=5: A and B remain accepted, C waits conditionally, and the plan remains confirmed and open. Two later min=2 responses allow C to join; cancellation recomputes without losing a still feasible core. Ordinary members see only the accepted count and never C's private minimum.

## AC-036 Exact waitlist action
A full range-based plan offers no waitlist action. A full exact-size plan exposes an explicit waitlist action and keeps waitlist order private.

## AC-037 Place slot and category mapping
For one Place/day, a slot compatible with five users wins over an earlier slot compatible with one user. Ties choose the earlier slot. The small `Бани и спа` category uses verified KudaGo v1.4 place slugs and content, and an unrelated beauty salon does not match it.

## AC-038 Saved places and batch repair
Saved places can be renamed, deleted when unused and marked default per city without exposing coordinates. A Signal's available origins follow its selected Companies' city. A recompute failure leaves neither partially committed Intent rows nor stale plans; a repeated owner refresh converges without duplicate plans.
