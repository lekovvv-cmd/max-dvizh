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

Core constraints: city, activity/category, time/recurrence, optional budget_max, optional origin/radius_km, min_people, max_people. A radius requires an origin; both may be omitted.

## AutoSignal recurrence
Keep MVP simple: weekdays + local start/end + IANA timezone + optional date bounds. Do not build a full rules language. The weekday is the local day on which the window starts; an end not later than the start means an overnight window.

## Provider item and source snapshot
Normalized external/model content exists in the provider adapter and temporary Redis cache; it is not a PostgreSQL catalogue. Only when matching creates a CandidatePlan do we persist one `CandidatePlanSourceSnapshot` with provider/provider ID/type, title/category, optional venue/coordinates/price/URLs, fetched timestamp and demo flag.

## CandidatePlan
Concrete feasible proposal being assembled.

Statuses: `COLLECTING`, `CONFIRMED`, `EXPIRED`, `CANCELLED` (add READY only if implementation truly needs it).

Contains a concrete source snapshot/activity/venue, concrete time, price representation, participant bounds and participant compatibility. For a collecting plan, `required_min_people == required_max_people == N`: every eventual participant must allow the selected final size N.

## Compatibility
Enum: `EXACT`, `NEAR`, `CONFLICT`, `UNVERIFIED`.
Computed by backend domain logic.

`UNVERIFIED` means provider data is insufficient to validate a constraint the user actually set. It creates neither an Offer nor a CandidatePlan by itself; it is not a rejection or a Conflict.

## Deviation
Structured reason for Near. MVP required: `BUDGET_OVER_MAX` with actual/limit/delta and safe user-facing text.

## Offer
Private invitation. A user's current pending Offer pool spans every group they belong to and is not product-capped.

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
