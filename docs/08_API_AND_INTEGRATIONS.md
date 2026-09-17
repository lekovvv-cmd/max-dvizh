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

## Runtime configuration

`APP_ENV=development` is the only mode that accepts `X-Demo-User`; every other value requires validated MAX init data. Compose passes all used backend settings, including MAX URLs/token, KudaGo settings, matching thresholds, TTLs and outbox retry/poll settings. Production must set `APP_ENV=production` and deployment secrets externally.
