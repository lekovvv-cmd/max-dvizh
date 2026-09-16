# 18 — Risks and non-goals

## Risks

### Cold start
Few active Intents → rare plans. Mitigation: existing friend groups, invites, persistent AutoSignals.

### Provider coverage
KudaGo coverage varies. Mitigation: provider abstraction, per-city quality policy, future official/partner source, honest demo data only where necessary.

### Price quality
Free-text/unknown. Mitigation: conservative parser, source text, unknown allowed.

### Privacy
Budget/location/intents private. Mitigation: backend aggregation, response minimization, authz tests.

### Matching complexity
Constraints combinatorial. Mitigation: target groups 4–12, bounded deterministic search, measure before optimizing.

### Concurrent acceptance
Plans compete for users. Mitigation: transactions, stale Offer handling, invalidation/recompute.

### MAX changes
Mitigation: isolate adapter and re-check official docs before freeze.

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
