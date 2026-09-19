# 08 — API and integrations

## Always verify current docs

The case explicitly warns that MAX docs evolve.

Current official roots to verify before coding/freeze:
- MAX docs: https://dev.max.ru/docs
- MAX Bot API: https://dev.max.ru/docs-api
- MAX Bridge: https://dev.max.ru/docs/webapps/bridge
- MAX UI: https://dev.max.ru/ui
- KudaGo API: https://docs.kudago.com/api/

Do not assume copied endpoint details stay current.

# MAX

## Required product uses

### Bot
Real product role:
- Mini App entry;
- Offer notification;
- `ДВИЖ СОБРАЛСЯ` notification;
- reminders if implemented.

### Mini App
Used for Signal/AutoSignal, locations/constraints, multiple Offers, Near confirmation, final plan.

### Deep links/start context
Use current supported mechanism for group invite, Offer and plan opening. Prefer opaque tokens, not sequential DB IDs.

### Share back
Use current supported Bridge/share mechanism for final plan. Current docs include `shareMaxContent`; verify exact contract before implementation.

## MAX identity
Never authorize using raw client `user_id`. Implement server-side validation exactly according to current official docs. If a launch mode has limitations, document them; do not invent validation.

# KudaGo

KudaGo currently documents a public API and calls it a free database of events and places. Current docs show `/public-api/v1.4/...`; verify current version before implementation.

Useful resources:
- locations;
- event categories;
- place categories;
- events;
- places;
- search.

Useful event data includes title, dates, place, location, categories, price, is_free, images, site_url.

Provider adapter normalizes to an in-memory `NormalizedLeisureItem` DTO. Redis caches query-specific normalized results; PostgreSQL saves a source snapshot only for a CandidatePlan created from one.

Suggested internal interface:
```text
LeisureProvider
- list_cities()
- list_items(query)
- get_item(id)
```

## Multi-city
Read supported cities from provider/config/data-quality policy. Never `if city == Kazan` in domain logic.

## Price
Store original `price_text`; parse conservative `price_min` only when safe; preserve free flag/source.

## Cache/fallback
Provider client needs timeout, bounded retry when useful, Redis cache-aside and freshness metadata. Event keys include city, exact start/end timestamps and a category hash; TTL is `LEISURE_CACHE_TTL_SECONDS`. A miss queries KudaGo with the same `location`, `actual_since`, `actual_until` and categories; a hit skips KudaGo. On provider failure a valid Redis value may be used; with no cache the API returns an honest unavailable/empty recovery state. Never silently replace live data with demo data or PostgreSQL catalogue rows.

## Provenance
Store provider/source URL/fetched_at and demo flag.

# Our API

Suggested route families (final contract may evolve):
```text
/api/v1/session
/api/v1/groups
/api/v1/groups/{id}/members
/api/v1/locations
/api/v1/intents
/api/v1/autosignals
/api/v1/offers  # all current user's pending offers across groups; no product cap
/api/v1/offers/{id}/accept
/api/v1/offers/{id}/reject
/api/v1/plans
/api/v1/plans/{id}
/api/v1/leisure/cities
```

Do not add CRUD merely because a table exists.

Because we have own API:
- keep OpenAPI exportable;
- maintain DATA-API.yaml with mandatory verification calls.

## Frontend response additions

`IntentOut` returns `weekdays`, `local_start` and `local_end` only for the current
user's recurring Intent. These safe display fields let the AutoSignals screen show
the owner's saved schedule; they do not expose another member's recurring rule and
do not alter matching or scheduler semantics.

## Implemented verification (2026-09-16)

The MAX Bridge is loaded from the official CDN `https://st.max.ru/js/max-web-app.js`. The client sends `window.WebApp.initData` to the backend as `X-MAX-Init-Data`; `app.modules.auth.service.validate_init_data` validates one `hash`, URL-decodes and sorts launch parameters, then applies the documented two-stage HMAC-SHA256 calculation and checks `auth_date`. Client data never authorizes a user by itself.

`window.WebApp.shareMaxContent({ text })` is used for a user-initiated final-plan share. The backend Bot API boundary uses documented `POST https://platform-api2.max.ru/messages?user_id=...` with `Authorization: <bot-token>` and an outbox. It does not send anything while `MAX_BOT_TOKEN` is absent.

To complete real MAX verification, the owner must create/register the bot and Mini App in MAX Business, deploy this app to HTTPS, set the token only in deployment, configure a HTTPS webhook and run the mobile/web walkthrough. This repository does not claim that external account step is complete.

## Product refactor verification (2026-09-18)

Current official MAX [Bridge](https://dev.max.ru/docs/webapps/bridge) documents signed `initData` with optional `chat: {id,type}`, `shareMaxContent`, and `start_param`. The [validation guide](https://dev.max.ru/docs/webapps/validation) still requires server-side two-stage HMAC. Chat binding accepts only a signed `CHAT` context and verifies bot access with [GET /chats/{chatId}](https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/); raw frontend chat IDs are never trusted. The [member endpoint](https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members) requires the bot to be a chat administrator, so the app does not claim member sync when the bot lacks that permission. MAX [Mini App deep links](https://dev.max.ru/docs/webapps/introduction) support `startapp` payloads with Latin letters, digits, underscore and hyphen up to 512 characters. Offer and plan notifications use opaque UUID payloads and direct Mini App links. `GET /chats` is unavailable since June 2026 per [MAX changelog](https://dev.max.ru/docs-api/changelog-api); the implementation never relies on it.

The official [KudaGo API](https://docs.kudago.com/api/) documents `events` with `expand=place`, distinct `places`, event/place category lists, city `timezone`, `next` pagination, place `timetable`, `is_closed` and coordinates. The adapter requests bounded event and place pages for each query slice. It does not infer an Event end or assert that free-text place opening hours are verified.

### Added own API contracts

- `POST /api/v1/signal-batches`, `PUT /api/v1/signal-batches/{id}`, `DELETE /api/v1/signal-batches/{id}`: atomic one-time Signal batch for same-city Companies.
- `PUT /api/v1/groups/{id}/city`: owner-only provider-validated Company city change. The response reports cancelled Signals, paused AutoSignals, cancelled collecting plans and invalidated Offers.
- `GET /api/v1/intents`: current user's own Intents across Companies, including safe owner-only display fields.
- `PUT /api/v1/autosignals/{id}` and existing pause/resume/cancel action route: recurrence management.
- AutoSignal create, edit and resume persist the rule and return immediately; a response background task evaluates the saved rule against the current seven-day provider slice with a separate database session. The periodic scheduler remains the fallback for later matching and provider recovery.
- `POST /api/v1/offers/{id}/cancel`: withdraw before cutoff and recompute affected plans.
- Offer/Plan responses now include accepted counts, remaining capacity, Company context, price kind and place opening-hours warning. Plan participant profiles are visible only after confirmation.

### Correctness update (2026-09-18)

The [official KudaGo category API](https://docs.kudago.com/api/) documents `/public-api/v1.4/place-categories/`. A live request to [the v1.4 list](https://kudago.com/public-api/v1.4/place-categories/?lang=ru&fields=slug,name) returned 54 place categories, including `salons`, `suburb`, `recreation`, and `amusement`, with no dedicated sauna/bath/spa slug. A live `salons` query in Moscow returned both a bath resort and unrelated beauty salons. The adapter therefore filters the internal `wellness` category by source category plus bath/spa wording in the title or description. The UI shows five small product categories and never exposes raw KudaGo slugs.

`GET /offers` and action responses distinguish `accepted_count` from `conditional_count`. `remaining_capacity` accounts for both accepted and conditional responders because both occupy an admission slot. `can_accept` and `can_waitlist` explicitly control the primary action; only exact-size overflow can waitlist. `GET /plans` reports `participant_count` for accepted members only and gives a conditional owner `personal_response_count` and `personal_required_min`. Other members never receive that personal minimum.

Saved place routes are `GET/POST /locations`, `PATCH /locations/{id}`, `POST /locations/{id}/default`, and `DELETE /locations/{id}`. Responses include the saved address text and default marker, never coordinates. A point can be created only for a city in one of the owner's Companies. Deleting a point referenced by an active Signal returns `409` with recovery guidance.

Company city update reuses existing city/timezone fields and Intent/plan/Offer statuses, so it requires no database migration. Supported slugs and timezone values come from the current KudaGo locations response; an arbitrary client slug is rejected.

One-time Signal batch create/edit fetches the provider slice before opening the mutation transaction. Intent rows, CandidatePlan/Offer recomputation and provider state commit together. Cancel also recomputes in the same transaction. Refresh re-fetches outside a write transaction, checks the batch is still current and applies an idempotent recompute. Place slots are evaluated on a bounded 30-minute grid and only the best feasible slot per Place/local day is materialized.

## Runtime configuration

`APP_ENV=development` is the only mode that accepts `X-Demo-User`; every other value requires validated MAX init data. Compose passes all used backend settings, including MAX URLs/token, KudaGo settings, matching thresholds, TTLs and outbox retry/poll settings. Production must set `APP_ENV=production` and deployment secrets externally.
## Provider state and retry

`GET /api/v1/intents` returns each user's `provider_state`. `POST /api/v1/signal-batches/{batch_id}/refresh` reruns the saved one-time Signal's provider query and matching; it is owner-only and does not create a new Signal. The Mini App presents distinct source-unavailable, no-source, and no-feasible-plan states with a retry action.
## Invite states

`POST /api/v1/groups/join/{token}` returns `404` for an unknown token and `410` for a known token whose optional `invite_expires_at` has passed. Existing and newly created links have no automatic expiry until a separate product policy sets one.
