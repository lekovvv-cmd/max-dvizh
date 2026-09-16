# 16 — Implementation plan

Build vertical slices; keep main runnable after each milestone.

## M0 — Repo/tooling
React/TS/Vite, FastAPI, Postgres, migrations, Docker, locks, lint/typecheck/tests. Exit: clean stack starts.

## M1 — MAX shell + identity
Real bot/Mini App boot, backend user mapping, current MAX validation, Home, mobile/web smoke.

## M2 — Groups/invites
Create group, membership/authz, invite/deep link, join flow.

## M3 — Locations + one-time Signal
Origin strategy, Signal form, private persistence, active/expired states.

## M4 — AutoSignals
Simple weekly recurrence, pause/resume, activity/budget/radius/group size.

## M5 — KudaGo + cache
Cities, event/place normalization, provenance, timeout, snapshot fallback, freshness UI.

## M6 — CandidatePlan engine
Time/category/budget/Haversine/group-size; Exact/Near/Conflict; bounded subset logic; unit tests.

## M7 — Offers
Rank max 3 overlap Offers; exact accept/reject; budget Near accept/reject; expiry.

## M8 — Conflict/recompute/concurrency
Accept one Offer; invalidate overlap; recompute; transaction-safe limits/races.

## M9 — ConfirmedPlan + MAX return
Confirmation, bot notification, deep-link plan, final share/return.

## M10 — Hardening
Provider failure, empty/error/refresh/repeat flow, privacy/authz tests, mobile/web polish.

## M11 — Submission
README, OpenAPI export, DATA-API.yaml, test-data instructions, Docker timing, presentation support, known limits, freeze checklist.

Do not start Could features before M0–M9 are stable. No AI/payments/booking/public feed/travel-time engine/second voting.
