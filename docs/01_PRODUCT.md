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
- city;
- available window;
- activity interests/categories;
- optional max budget;
- optional origin and radius km;
- min/max people.

Signal expires.

## AutoSignal

Recurring “invite me if these conditions occur”. Examples:
- Fridays after 18:00;
- always if sauna;
- PC club only if exactly 5 people.

AutoSignal never means attendance. It only makes a user eligible for an Offer.

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
- potential compatible users;
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

If exactly 5 and 6 users are compatible, build a valid subset of 5. Remaining user is not publicly “excluded”; they may remain reserve/eligible elsewhere.

## Distance

MVP uses user-owned origin coordinates + straight-line/geodesic km. No travel-time estimate.

Origin choices: Home, University, Work, Current location, map/manual point.

Offer shows only that user's own distance.

## Multi-city

MVP works in every city with sufficient provider data. Do not hardcode Kazan. Pilot can be 1–3 cities; product geography is separate.

## Leisure data

Initial real provider: KudaGo, behind provider abstraction.

If provider does not cover a use case, do not fake live data. Explicit model/demo data is allowed only when clearly labeled.

## Price

- authoritative free flag → 0;
- safely parsed minimum may be approximate;
- unknown → omit price from the UI; it is Unverified only when the user set a budget limit;
- preserve original source price text.

## User-facing state language

Prefer:
- «Есть потенциал»;
- «Собираем»;
- «ДВИЖ СОБРАЛСЯ».

Internal terms like CandidatePlan are not primary UI language.

## Non-goals online MVP

No AI/LLM, public feed, payment, booking engine, realtime traffic, friend ranking, ML recommender, second voting stage, manually curated all-Russia catalog.
