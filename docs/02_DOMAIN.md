# 02 — Domain model

## User
MAX user mapped to internal user. Client-submitted identity is never trusted without server-side validation per current official MAX docs.

## Group
Private friend-company context. May be associated with MAX chat context, but domain must work without it. Fallback: internal Group + invite deep link/start parameter.

## Location
User-owned origin point: label, lat/lon, city, kind (saved/current/manual), owner. Private by default.

## Intent
User willingness under conditions.

Types: `ONE_TIME`, `RECURRING`.
Statuses: `ACTIVE`, `PAUSED`, `EXPIRED`, `CANCELLED`.

Core constraints: city, activity/category, time/recurrence, budget_max, origin, radius_km, min_people, max_people.

## AutoSignal recurrence
Keep MVP simple: weekdays + local start/end + optional date bounds. Do not build a full rules language.

## LeisureItem
Normalized external/model content.

Must carry provenance: provider, provider_id, URL if available, fetched_at, is_demo/model.

## CandidatePlan
Concrete feasible proposal being assembled.

Statuses: `COLLECTING`, `CONFIRMED`, `EXPIRED`, `CANCELLED` (add READY only if implementation truly needs it).

Contains concrete LeisureItem/activity/venue, concrete time, price representation, participant bounds, participant compatibility.

## Compatibility
Enum: `EXACT`, `NEAR`, `CONFLICT`.
Computed by backend domain logic.

## Deviation
Structured reason for Near. MVP required: `BUDGET_OVER_MAX` with actual/limit/delta and safe user-facing text.

## Offer
Private invitation.

Statuses: `PENDING`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `INVALIDATED`.

Near Offer requires explicit exception confirmation.

## ConfirmedPlan
A CandidatePlan is confirmed only when:
- accepted >= min_people;
- accepted <= max_people;
- all Near deviations explicitly approved;
- no participant has overlapping ConfirmedPlan;
- plan/source/time is valid under project policy.

## Reservation/conflict
Accepted Offer may reserve a user's time while plan finalizes. Overlapping offers/candidates must be recomputed transactionally.

## Waitlist
SHOULD, not MUST. If implemented, never expose “you were excluded”.

## Aggregate potential
Product may show counts (exact active, compatible AutoSignals, potential total) without exposing identities before reveal/acceptance.
