# 01 — Product spec: MAX ДВИЖ

## Statement

**ДВИЖ** — MAX Mini App + bot that takes a friend group from “maybe go somewhere?” to a concrete feasible leisure plan.

> **ДВИЖ does not match people. It assembles concrete plans that the required people can actually accept.**

## Primary segment

Young people 18–25, friend groups 4–12, already coordinating in group chats, often planning on short notice.

## Problem

People don't only need “where to go”. They need to discover who is willing under what conditions while reconciling time, budget, activity, individual distance and group size. Manual coordination is long and often dies.

## User result

Not a feed/catalog. Result is a **ConfirmedPlan** with concrete what/where/when and confirmed participants.

## As Is

```text
«Кто сегодня гулять?»
→ replies/silence
→ time
→ budget
→ activity
→ search places/events
→ links
→ too far/expensive/wrong group size
→ discussion restarts
→ plan or nothing
```

## To Be

```text
Intent
→ CandidatePlans
→ Exact/Near/Conflict
→ full private Offer pool
→ user chooses
→ enough confirmations
→ ConfirmedPlan
→ MAX
```

## Signal

One-time “I am open to plans in this window”.

MVP fields:
- one or more companies in one city; city comes from Company;
- available window;
- activity interests/categories;
- optional max budget;
- optional origin and radius km;
- minimum people and optional explicit maximum.

Signal expires after its availability window with a small server-side grace. The main UI offers quick time presets and lets a person send without opening optional conditions. A batch across several companies is created, edited and cancelled atomically.

## AutoSignal

Recurring “invite me if these conditions occur”. Examples:
- Fridays after 18:00;
- always if sauna;
- PC club only if exactly 5 people.

AutoSignal never means attendance. It only makes a user eligible for an Offer.
The scheduler evaluates active rules every 30 minutes across a seven-day lookahead, and immediately after create, edit or resume.

## Compatibility

### Exact
All required conditions fit.

### Near
Small supported deviation. Online MVP MUST support budget Near.

Example: max 300 ₽, plan 400 ₽, delta within configured Near threshold. User receives a private explicit exception Offer and is not counted until accepting.

### Conflict
Hard mismatch; no normal Offer.

### Unverified
The user set a hard constraint but the provider lacks the fact needed to validate it—for example, no price with a budget limit or no coordinates with a radius. It is not a Conflict, but also is not eligible and creates no Offer.

## Near privacy

Other users must not see the person's exact budget or reason. Aggregate wording is allowed: “ещё 1 человек сможет присоединиться, если согласится на небольшое превышение бюджета”.

## CandidatePlan

Concrete enough to accept/reject:
- city;
- activity/event/place;
- venue/source;
- start/end;
- price status;
- min/max participants;
- current accepted count and remaining capacity;
- provenance/freshness.

CandidatePlan is not a meeting yet.

## Offer

Private invitation to a CandidatePlan.

A user sees the full current pool of personally addressed pending Offers, including offers from every one of their groups and both Exact and Near compatibility. The system may sort for convenience but **never chooses socially for the user or discards a ranked Offer**.

Example:
```text
🎳 Боулинг 20:00–22:00 · ~700 ₽ · 2.1 км · 3 чел.
🎮 ПК-клуб 20:00–23:00 · ~350 ₽ · 3.4 км · 4 чел.
[choose one] [pass]
```

## No separate voting

No Blind Consensus stage. Offer selection is the vote. Do not add points/veto after a concrete Offer already exists.

## Overlapping plans

Accepting one Offer reserves the user's time; overlapping pending Offers/candidates are invalidated/recomputed. Independent non-overlapping plans may continue.

## Group size

Inputs:
- any;
- min N;
- range N..M;
- N or more;
- exactly N.

The main presets are `Неважно` (min=2), `Хотя бы 3` and `Хотя бы 5`, all without an explicit maximum. In that case capacity is the current Company size. All compatible members receive Offers. The plan confirms at the accepted minimum and stays open until capacity or cutoff. `Ровно N` is advanced: the first N successful acceptances take places; later responses enter a private waitlist and the first eligible waitlisted person is promoted after a cancellation.

## Distance

MVP uses user-owned origin coordinates + straight-line/geodesic km. No travel-time estimate.

Saved places are optional and can be labelled Home, University, Work or Other. Creation uses real device geolocation; no default or fabricated coordinates. Without a saved place, radius matching is unavailable.

Offer shows only that user's own distance.

## Multi-city

MVP works in every city with sufficient provider data. Do not hardcode Kazan. Pilot can be 1–3 cities; product geography is separate.

## Leisure data

Initial real provider: KudaGo, behind provider abstraction.
Events and Places are distinct. Every verified Event occurrence is a separate concrete candidate. Places receive concrete two-hour slots on a 30-minute grid and visibly warn when opening hours cannot be verified.

If provider does not cover a use case, do not fake live data. Explicit model/demo data is allowed only when clearly labeled.

## Price

- authoritative free flag → 0;
- exact price and `от N ₽` price floor are distinct; the floor may allow an Offer but the UI warns that the final price can be higher;
- unknown → omit price from the UI; it is Unverified only when the user set a budget limit;
- preserve original source price text.

## User-facing state language

Prefer:
- «Сигнал активен»;
- «Собираем»;
- «ДВИЖ СОБРАЛСЯ».

Internal terms like CandidatePlan are not primary UI language.

## Non-goals online MVP

No AI/LLM, public feed, payment, booking engine, realtime traffic, friend ranking, ML recommender, second voting stage, manually curated all-Russia catalog.
