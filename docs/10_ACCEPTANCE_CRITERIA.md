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
6 compatible, max=5 → valid subset of 5; sixth is not publicly labelled excluded.

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
No reliable price → no invented number and no placeholder row in UI. When budget is a hard constraint, this item is not compatible.

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
