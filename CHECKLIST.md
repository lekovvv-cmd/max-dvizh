# Master checklist

## Product
- [ ] problem evidence collected / research plan exists
- [x] one priority flow
- [x] Signal
- [x] AutoSignal
- [x] Near budget
- [x] multiple overlapping Offers
- [x] all compatible users receive Offers; confirmation stays open until maximum
- [x] exact-N waitlist and cancellation before cutoff
- [x] atomic multi-company Signal batch and active Signal controls
- [x] periodic AutoSignal scheduler and edit/pause/delete
- [x] Events and Places with occurrence/price provenance
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
- [x] modular monolith
- [x] Postgres migrations
- [x] no working secrets committed (repository scan; deployment secrets remain external)
- [x] dependency locks
- [x] unit and PostgreSQL integration tests
- [ ] full browser/MAX E2E matrix
- [x] concurrency locking strategy and PostgreSQL migration CI
- [x] error recovery
- [x] Docker one-command
- [x] build <=5 min target (GitHub Actions Docker job: 28 s with cached base images)

## Submission
- [x] README updated for product rework
- [x] OpenAPI exported after API changes
- [x] DATA-API.yaml
- [ ] test accounts/data
- [ ] HTTPS deployment
- [ ] presentation PDF
- [ ] technical slide
- [ ] commit hash frozen
- [x] known limitations documented
