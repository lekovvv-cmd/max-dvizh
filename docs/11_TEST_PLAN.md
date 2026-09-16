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
- reserve if implemented.

### Budget
- Exact;
- Near;
- Conflict;
- unknown price.
- unknown price with budget → Conflict; missing venue coordinates with radius → Conflict.

### Distance
- Haversine known values;
- radius boundary;
- missing coords.

### Offers
- create/accept/reject/expire/invalidate.

### Conflicts
- accept one overlapping Offer;
- other candidate recomputes;
- non-overlap unaffected.

### AutoSignal
- weekday/time match;
- mismatch;
- paused;
- timezone.

## Integration tests
- PostgreSQL repositories;
- concurrent Offer acceptance;
- provider normalization;
- cache fallback;
- Redis hit/miss and provider-failure fallback without PostgreSQL catalogue rows;
- CandidatePlan source snapshot creation and readability after Redis eviction;
- mocked MAX boundary;
- identity validation adapter.

## API tests
At minimum: session, groups/join, locations, Intents/AutoSignals, Offers list, exact accept, Near accept with explicit confirmation, reject, plans, leisure cities. Verify authz, 4xx/409 and privacy.

## E2E
1. Signal → CandidatePlan → Offer → ConfirmedPlan.
2. Near 300→400.
3. Five cross-group pending Offers (Exact and Near) are all accessible; overlapping recomputation still applies after acceptance.
4. Provider outage with cache/freshness.
5. Deep-link/group join.

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
