# 15 — Pilot, metrics, scaling

## Product geography
MVP is multi-city where provider data quality is sufficient. Product geography != pilot geography.

## Pilot suggestion
- 100–200 users;
- 20–40 friend groups;
- 1–3 cities;
- 2–3 weeks.

These are hypotheses, not facts.

## Pilot hypothesis
If ДВИЖ privately captures reusable participation conditions and turns them into concrete Offers, friend groups will reach a confirmed leisure plan with fewer coordination actions and less time than ordinary chat planning.

## Primary metric
**Plan Conversion** — share of eligible Intent episodes reaching ConfirmedPlan. Define denominator explicitly before reporting.

## Secondary metric
**Time to Plan** — time from first relevant collection/Intent to ConfirmedPlan.

Do not claim measured improvement before measuring. Targets must be labelled as hypotheses.

## Supporting metrics
- Offer Acceptance Rate;
- Near Acceptance Rate;
- AutoSignal trigger-to-accept;
- CandidatePlan→ConfirmedPlan;
- repeat usage;
- AutoSignal retention;
- median Offers shown before acceptance.

## Research before submission
Aim for 10–20 short interviews. Separate findings from assumptions.

## Scaling core
Unchanged: Intent, AutoSignal, compatibility, CandidatePlan, Offer, ConfirmedPlan, privacy model, MAX interaction, architecture.

Variable: provider data, city mapping, categories, partners, source quality, local official integrations.

## Scaling path
1. All sufficiently covered cities of initial provider.
2. Add adapters for data gaps.
3. Add official/partner sources.
4. City/organization launch playbooks.
5. Booking/commercial integrations only after core value validation.
