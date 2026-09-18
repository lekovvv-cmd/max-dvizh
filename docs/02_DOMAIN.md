# 02 — Domain model

## User
MAX user mapped to internal user. Client-submitted identity is never trusted without server-side validation per current official MAX docs.

## Group
Private friend-company context with one provider-supported city and timezone. It may be bound to a group chat only from validated MAX launch context; private Company creation uses an invite deep link.

## Location
Optional user-owned place: label, real coordinates, optional address text, city, kind and owner. Private by default. Radius matching requires a saved place in the Company city.

## Intent
User willingness under conditions.

Types: `ONE_TIME`, `RECURRING`.
Statuses: `ACTIVE`, `PAUSED`, `EXPIRED`, `CANCELLED`.

Core constraints: Company-inherited city, category set, time/recurrence, optional budget_max, optional origin/radius_km, min_people, nullable explicit max_people. A radius requires an origin; both may be omitted. One-time Signal rows may share a `signal_batch_id` across several same-city companies.

## AutoSignal recurrence
Keep MVP simple: weekdays + local start/end + IANA timezone + optional date bounds. Do not build a full rules language. The weekday is the local day on which the window starts; an end not later than the start means an overnight window.

## Provider item and source snapshot
Normalized external/model content exists in the provider adapter and temporary Redis cache; it is not a PostgreSQL catalogue. Only when matching creates a CandidatePlan do we persist one `CandidatePlanSourceSnapshot` with provider/provider ID/type, title/category, optional venue/coordinates/price/URLs, fetched timestamp and demo flag.

## CandidatePlan
Concrete feasible proposal being assembled.

Statuses: `COLLECTING`, `CONFIRMED_OPEN`, `CONFIRMED`, `EXPIRED`, `CANCELLED`. `CONFIRMED` is full or past the joining cutoff.

Contains a concrete source snapshot/activity/venue, concrete time, price representation, minimum to confirm, effective capacity and private participant compatibility. Confirmation is permitted only when every accepted person's personal size range allows the count. A confirmed plan remains open until capacity or cutoff.

## Compatibility
Enum: `EXACT`, `NEAR`, `CONFLICT`, `UNVERIFIED`.
Computed by backend domain logic.

`UNVERIFIED` means provider data is insufficient to validate a constraint the user actually set. It creates neither an Offer nor a CandidatePlan by itself; it is not a rejection or a Conflict.

## Deviation
Structured reason for Near. MVP required: `BUDGET_OVER_MAX` with actual/limit/delta and safe user-facing text.

## Offer
Private invitation. A user's current pending Offer pool spans every group they belong to and is not product-capped.

Statuses: `PENDING`, `WAITING_CONDITION`, `ACCEPTED`, `WAITLISTED`, `REJECTED`, `EXPIRED`, `INVALIDATED`, `CANCELLED_BY_USER`. Conditional responders are shown privately as interested but are not confirmed participants until their minimum is met.

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
Required for exact N. All compatible users first receive Offers; response time determines admission, and later responders are privately waitlisted. Only the owner sees their waitlist state. Cancellation before cutoff promotes the first eligible waitlisted responder.

## Aggregate potential
Before confirmation, show only accepted/needed counts without identities. After confirmation, basic profiles of accepted participants may be shown; waitlisted identities and private constraints never appear.
