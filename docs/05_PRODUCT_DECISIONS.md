# 05 — Product decisions / ADR log

Do not reverse without explicit team approval.

## ADR-001 — Match plans, not people
Accepted. “Three people are free” is not a plan.

## ADR-002 — No separate Blind Consensus
Accepted. CandidatePlan/Offer is already concrete; Offer choice is the vote.

## ADR-003 — Multiple overlapping Offers are user-selected
Superseded by ADR-014 and ADR-015. Never choose socially for user.

## ADR-004 — Near exists
Accepted. MVP Near = budget. Always explicit acceptance.

## ADR-005 — Distance, not travel time
Accepted. Kilometers from user-selected origin; no minute estimate in MVP.

## ADR-006 — AutoSignals persist
Accepted. “Fridays / sauna / exactly 5” should not require daily check-in. Trigger ≠ attendance.

## ADR-007 — Multi-city MVP
Accepted. Not Kazan-only. Pilot geography separate.

## ADR-008 — No AI
Accepted. Not needed; adds risk and violates scope discipline.

## ADR-009 — KudaGo initial provider
Accepted for initial implementation behind provider adapter.

## ADR-010 — Backend privacy
Accepted. Do not send private raw data to other clients.

## ADR-011 — Modular monolith
Accepted. No microservices for hackathon MVP.

## ADR-012 — FastAPI + React/Vite + PostgreSQL
Accepted default unless real blocker appears.

## ADR-013 — CandidatePlan must be concrete
Accepted. “Я в деле” must have clear what/when/where/price status/own distance/participant requirement.

## ADR-014 — Unlimited Offer pool
Accepted. Product logic never caps the number of current pending Offers. Ranking and pagination may improve navigation but must not discard a compatible Offer.

## ADR-015 — Offer pool is cross-group
Accepted. `GET /offers` is global to the current user and every Offer exposes safe group ID and name.

## ADR-016 — Redis is the provider catalogue cache
Accepted. KudaGo query responses/normalized DTOs use parameterized Redis keys and TTL; PostgreSQL is not a cache fallback.

## ADR-017 — Persist source snapshot only for CandidatePlan
Accepted. One stable provider-item snapshot is saved only when a concrete CandidatePlan is created.

## ADR-018 — Omit missing optional UI metadata
Accepted. UI omits unavailable optional rows rather than printing “unknown”.

## ADR-019 — Unknown hard-constraint data is incompatible
Superseded by ADR-020. Such an item is not eligible for an Offer.

## ADR-020 — Unverified differs from Conflict
Accepted. Absence of provider facts necessary to verify a user-set budget/radius is `UNVERIFIED`: it is neither a verified match nor a known mismatch. It never creates an Offer and cannot alone create a CandidatePlan.

## ADR-021 — Constraints are optional and cache is query-scoped
Accepted. Budget and radius are opt-in hard constraints. Redis cache-aside keys represent the actual city/time/category query needed for an Intent, never a whole-city provider catalogue.

## ADR-022 — Exact final group size is selected deterministically
Superseded by ADR-024. A preliminary feasible size must never silently select which compatible friends receive Offers.

## ADR-023 — AutoSignal is local-time aware
Accepted. Recurrence stores IANA timezone in its private JSON rule. A complete provider event interval must fit the weekday/window after UTC conversion. Overnight end times are supported as a window ending the following local day.

## ADR-024 — Open plans and private waitlist
Accepted. Every compatible member receives a private Offer. `Неважно` means min=2 and no explicit max; other primary presets mean min=3 or 5 with no explicit max. Effective max is the current company size. The plan confirms when enough accepting users satisfy every accepted member's range, then stays open for further compatible joins until capacity or cutoff. Explicit `Ровно N` admits the first N successful acceptances and privately waitlists later responses in response order. Cancellation before cutoff promotes the first eligible waitlisted member. Neither Offer ranking nor Intent enumeration decides who may respond.

One compatible member may start a concrete CandidatePlan and receive an Offer even when fewer than N members have signalled. N is the confirmation threshold, not the plan creation threshold. A personal minimum above the current Company capacity cannot yield an Offer.

## ADR-025 — One Signal batch, one city
Accepted. A one-time Signal may address multiple companies in the same provider-supported city. Creation, edit and cancellation are atomic for the whole batch. Company owns city; the client does not choose it per Signal. Signal expiry is derived server-side from the availability window. A saved location is optional; distance matching requires a real, user-owned location in that city.

## ADR-026 — Recurring evaluation and concrete provider facts
Accepted. Active AutoSignals are evaluated immediately when created, edited or resumed and periodically every 30 minutes over seven days. KudaGo Events and Places are separate normalized sources; a Place produces a concrete time slot. An Event without a verified end creates no normal Offer. `FROM` price is a floor with an explicit uncertainty label, while `UNKNOWN` is Unverified only when a budget was set. Provider catalogue data remains in query-scoped Redis; only CandidatePlan snapshots are persisted.
## ADR-027 — Приглашение с необязательным сроком

У ссылки Company есть nullable `invite_expires_at`. Отсутствие срока сохраняет действующее поведение уже выданных ссылок и не вводит скрытый период жизни. Если срок установлен и прошёл, backend возвращает `410` с отдельным состоянием «Приглашение истекло»; неизвестный токен возвращает `404` «Приглашение недействительно».

## ADR-028 — Confirmed core and conditional responders

Accepted. An already feasible confirmed core remains confirmed when a new responder has a stricter personal minimum. That responder is `WAITING_CONDITION` until a feasible set including them exists. Recompute prefers retaining existing accepted participants, then the largest feasible set, with response order as the deterministic tie-breaker. Cancellation may demote participants whose personal conditions are no longer satisfied, while retaining the remaining feasible core. `accepted_count` and visible participant identities include only `ACCEPTED`; each conditional user's own required minimum and progress are owner-only.

## ADR-029 — Place slot and wellness taxonomy

Accepted. For each bounded Place and local day, choose the slot with the largest feasible group, then the most compatible members, then the earliest start. Materialize one CandidatePlan per Place/day. KudaGo's live v1.4 place categories have no dedicated bath/sauna/spa slug; the small internal `wellness` category uses real `salons`, `suburb`, `recreation`, and `amusement` source slugs plus a bath/spa term in the place's title or description. Raw provider slugs are never a main UI selector.

## ADR-030 — Saved origin and Signal batch consistency

Accepted. Saved places are private, city-scoped GPS points. The user may rename, delete an unused point, and set one default per city. A location used by an active Signal cannot be deleted until the distance condition is removed. Signal batch provider I/O finishes before the database mutation; Intent changes, plan recomputation and provider state commit together. A failed recomputation rolls the mutation back, and owner refresh is idempotent.

## ADR-031 — Explicit Company city change

Accepted. Only the Company owner may choose a new city, and the backend accepts only a current provider-supported city. The change updates the Company's provider slug and timezone in one transaction. Active one-time Signals are cancelled, active AutoSignals are paused, COLLECTING plans are cancelled, and their active Offers are invalidated. A CONFIRMED_OPEN plan keeps its accepted core and original facts, while pending, conditional and waitlisted Offers are invalidated so the old-city plan no longer collects new participants. Confirmed plans and user-owned saved locations are not rewritten or deleted.
