# 12 — Security and privacy

## Never expose across users
- exact origin/address;
- exact budget;
- private Intent/AutoSignal;
- rejection;
- Near reason;
- private compatibility.
- waitlist identity and membership before a plan is confirmed.

## MAX identity
Validate server-side using current official MAX docs. Do not authorize from client-submitted user_id.
Chat-bound Company creation uses only the signed launch chat context and verifies bot access to that chat. A client-supplied chat ID is never authoritative.

## Authorization
Every route checks authenticated user and group/resource membership/ownership.

Prefer opaque invite/deep-link tokens.

## Secrets
Never commit MAX token, DB password, API keys, signing secrets. `.env.example` only contains names/safe defaults.

## Logging
Do not log tokens/full auth payloads or unnecessary exact coordinates/private rules.

## Location
Saved locations are user-owned and require a real user-provided GPS point. No hardcoded coordinates are submitted. Radius matching is disabled until a point exists; never show friend locations on maps.

## Concurrency/idempotency
Offer state changes use PostgreSQL row locks in User → CandidatePlan → Offer order. Repeating the same final action is idempotent; an opposite final action conflicts. Outbox dedupe keys prevent duplicate logical notifications.

## Rate limiting
Protect join/invites, Offer actions, provider sync and bot webhook as appropriate.

## Dependencies/license
Use maintained OSS with suitable licenses; case forbids unauthorized closed/private code.

## User controls
Users can delete saved locations, edit/cancel one-time Signal batches, pause/edit/delete AutoSignals, and cancel accepted participation before cutoff. Document retention limitations.
