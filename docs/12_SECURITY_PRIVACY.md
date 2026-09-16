# 12 — Security and privacy

## Never expose across users
- exact origin/address;
- exact budget;
- private Intent/AutoSignal;
- rejection;
- Near reason;
- private compatibility.

## MAX identity
Validate server-side using current official MAX docs. Do not authorize from client-submitted user_id.

## Authorization
Every route checks authenticated user and group/resource membership/ownership.

Prefer opaque invite/deep-link tokens.

## Secrets
Never commit MAX token, DB password, API keys, signing secrets. `.env.example` only contains names/safe defaults.

## Logging
Do not log tokens/full auth payloads or unnecessary exact coordinates/private rules.

## Location
Saved locations are user-owned; current location should be ephemeral where possible; never show friend locations on maps.

## Concurrency/idempotency
Offer state changes need transactional consistency and stale-request handling.

## Rate limiting
Protect join/invites, Offer actions, provider sync and bot webhook as appropriate.

## Dependencies/license
Use maintained OSS with suitable licenses; case forbids unauthorized closed/private code.

## User controls
If time permits: delete location, pause/delete AutoSignal, leave group. Document retention limitations.
