# 11 — Test plan

## Unit domain tests

### Time
- overlap;
- no overlap;
- boundaries;
- city timezone conversion.

### Participant count
- min;
- max;
- range;
- exactly N;
- pool > max;
- first-response admission and private waitlist for exact N;
- all compatible users receive Offers even when their count exceeds capacity;
- confirmation at minimum with further admission until effective maximum;
- mixed minimums keep responders in collecting until all ranges allow final N;
- deterministic mixed ranges, exact-5 below/at threshold and Intent-order independence.

### Budget
- Exact;
- Near;
- Conflict;
- unknown price without budget → Exact on budget dimension;
- unknown price with budget → Unverified; missing venue coordinates with radius → Unverified;
- known hard mismatch → Conflict.

### Distance
- Haversine known values;
- radius boundary;
- missing coords.

### Offers
- create/accept/reject/expire/invalidate.
- dynamic TTL: min(6 hours, half the time until start), with 10-minute cutoff;
- cancellation and waitlist promotion before cutoff.

### Conflicts
- accept one overlapping Offer;
- other candidate recomputes;
- non-overlap unaffected.

### AutoSignal
- weekday/time match;
- mismatch;
- paused;
- timezone.
- complete interval containment and overnight local windows.
- periodic scheduler tick on an IANA local-time window; edit/pause/delete.

## Integration tests
- PostgreSQL repositories;
- concurrent Offer acceptance;
- provider normalization;
- cache fallback;
- Redis hit/miss and provider-failure fallback without PostgreSQL catalogue rows;
- cache-aside key partitioning by city, requested time range and categories;
- CandidatePlan source snapshot creation and readability after Redis eviction;
- no CandidatePlan/source snapshot when every evaluated user is Unverified/Conflict;
- mocked MAX boundary;
- KudaGo valid/missing/invalid/multiple-date normalization;
- KudaGo Events and Places, pagination, occurrences, uncertain opening hours and FROM price;
- atomic multi-company Signal batch with city validation;
- provider-state persistence and owner-only retry for active Signal empty states;
- outbox retry, claim and OFFER/CONFIRMED_PLAN delivery;
- clean PostgreSQL Alembic upgrade to head.
- identity validation adapter.

## API tests
At minimum: session, groups/join, locations, Intents/AutoSignals, Offers list, exact accept, Near accept with explicit confirmation, reject, plans, leisure cities. Verify authz, 4xx/409 and privacy.

## E2E
1. Signal → CandidatePlan → Offer → ConfirmedPlan.
2. Near 300→400.
3. Five cross-group pending Offers (Exact and Near) are all accessible; overlapping recomputation still applies after acceptance.
4. Provider outage with cache/freshness.
5. Deep-link/group join.
6. One-screen Signal across two companies; edit and cancel from Home.
7. Eight compatible members receive Offers; three confirm a plan and later members join until capacity.
8. Exact-five queue promotes first waiter after cancellation; mixed minimums never confirm early.
9. AutoSignal scheduler creates an Offer without the user visiting the app.

## Manual real MAX QA
- mobile;
- web;
- bot entry;
- Mini App;
- notification;
- deep link;
- final share/return.

Browser tests do not replace real MAX QA.

## Performance smoke
Target groups 4–12. Measure CandidatePlan generation on representative provider item count.

## Security checks
Secret scan, dependency audit where available, object access/authz, privacy leakage, invalid/stale MAX identity, unauthorized group access.

## Submission smoke
Clean clone → env → Docker build/start → migrations → core E2E twice → OpenAPI export → README verify → commit hash → working MAX deployment.
