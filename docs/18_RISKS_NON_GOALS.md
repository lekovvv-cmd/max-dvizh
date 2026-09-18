# 18 — Risks and non-goals

## Risks

### Cold start
Few active Intents → rare plans. Mitigation: existing friend groups, invites, persistent AutoSignals.

### Provider coverage
KudaGo coverage varies. Mitigation: provider abstraction, per-city quality policy, future official/partner source, honest demo data only where necessary.

### Price quality
Free-text/unknown and FROM prices. Mitigation: preserve source text and uncertainty; unknown price never satisfies a budget cap. FROM is treated as a lower bound and is shown as such.

### Privacy
Budget/location/intents private. Mitigation: backend aggregation, response minimization, authz tests.

### Matching complexity
Constraints combinatorial. Mitigation: target groups 4–12, bounded deterministic search, measure before optimizing.

### Concurrent acceptance
Plans compete for users. Mitigation: database locks, stable lock ordering, stale Offer handling, query-time expiry and snapshot-based invalidation/recompute.

### MAX changes
Mitigation: isolate adapter and re-check official docs before freeze.

### Place opening hours
KudaGo opening-hour data is incomplete or nonuniform. Generated place slots are labelled unverified; users must check the source before travel. A place without a credible URL or city match is not offered.

### External verification
An owner-controlled MAX bot token, public HTTPS Mini App and live MAX mobile/web test are still required. Local development and model data cannot establish real in-MAX completion.

## Non-goals online MVP
- every venue in Russia;
- booking/payment;
- route/travel-time accuracy;
- traffic/transit engine;
- AI/chat understanding;
- reading chat history;
- automatic attendance;
- public people discovery/social feed;
- complex post-confirm rescheduling.
