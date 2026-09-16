# Master checklist

## Product
- [ ] problem evidence collected / research plan exists
- [ ] one priority flow
- [x] Signal
- [x] AutoSignal
- [x] Near budget
- [x] multiple overlapping Offers
- [x] user chooses Offer
- [x] exact group-size constraints
- [x] individual km distance
- [x] ConfirmedPlan
- [x] no Blind Consensus reintroduced
- [x] not Kazan-only

## MAX
- [ ] real bot role — code/config ready; requires owner MAX bot/account
- [x] Mini App connected to bot
- [ ] mobile verified
- [ ] web verified
- [x] deep-link/start flow
- [x] Offer notification — independent outbox worker/Bot API adapter ready; requires configured token
- [x] final share/return
- [x] current docs checked before freeze

## Data
- [x] real provider
- [x] multi-city
- [x] provenance
- [x] price uncertainty
- [x] Redis provider cache/fallback (no PostgreSQL provider catalogue)
- [x] demo data labelled

## Technical
- [ ] modular monolith
- [x] Postgres migrations
- [ ] no secrets
- [x] dependency locks
- [ ] unit/integration/E2E — domain and API smoke included; full browser/MAX matrix remains
- [x] concurrency locking strategy and PostgreSQL migration CI
- [x] error recovery
- [x] Docker one-command
- [ ] build <=5 min target

## Submission
- [x] README complete
- [ ] OpenAPI exported — run after deployed image refresh
- [x] DATA-API.yaml
- [ ] test accounts/data
- [ ] HTTPS deployment
- [ ] presentation PDF
- [ ] technical slide
- [ ] commit hash frozen
- [ ] known limitations
