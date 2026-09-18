# 04 — User flows

## A. First entry from MAX
1. Open bot/entry in MAX.
2. Open Mini App.
3. Backend validates MAX launch identity/context using current official rules.
4. Create/join/select Group.
5. Home.

## B. Join via invite/deep link
1. Member shares invite in MAX.
2. Recipient opens link.
3. Mini App receives supported start context.
4. Backend resolves invite.
5. Join confirmation.

Handle invalid/expired/already-member.

## C. One-time Signal
1. Home → `⚡ Подать сигнал`.
2. Select a quick time, categories and one or more same-city companies. Optional conditions are collapsed.
3. Submit.
4. Private confirmation; do not leak others.
5. Backend recomputes CandidatePlans.
6. User later receives Offer(s).

## D. AutoSignal
1. AutoSignals → Add.
2. Name, Company, categories, weekdays, local time and optional budget, saved place/radius and group size.
3. Save.
4. Browser IANA timezone is submitted with weekdays and local start/end; it remains active until paused/deleted.
5. Immediate and periodic matching (every 30 minutes, seven-day lookahead) → Offer.
6. User must accept.

## E. Exact Offer
Show activity/place, local time, source-aware price, own distance, group state, expiry if any. Actions: `Я в деле`, `Пас`.

## F. Near budget Offer
Given max=300, plan=400 within Near threshold:
```text
Цена: 400 ₽
Твой лимит: 300 ₽
На 100 ₽ выше
[ Всё равно пойду ] [ Пропустить ]
```
User is not counted until explicit acceptance; others do not see exact budget.

## G. Offer pool across companies
Show every current pending Offer addressed to the user, across all their companies and including Exact and Near. Each card identifies its company. Sorting is allowed, product truncation is not. User chooses one; backend accepts selected and invalidates/recomputes only overlapping ones. No automatic selection.

## H. Group size and waitlist
Every eligible person receives an Offer. `Неважно` starts at two people; no explicit maximum means the current Company size. At the minimum the plan becomes confirmed but remains open. For advanced `Ровно N`, the first N successful responses are admitted and subsequent responses are privately waitlisted. Cancellation before cutoff promotes the first eligible waitlisted person.

## I. Confirmed plan
Enough valid confirmations → `⚡ ДВИЖ СОБРАЛСЯ`; more may join until capacity/cutoff. Bot notification; Mini App detail; final share/return in MAX. A person can withdraw before cutoff.

## J. Provider unavailable
Timeout/failure → valid Redis cache if allowed; show freshness. Without cache, show an honest recovery/empty state. If model data is deliberately used, label it explicitly.

## K. No exact plan
Do not dead-end. If a private Near path exists, invite the relevant user privately. Never say “Андрей мешает из-за бюджета”.

## L. Missing provider facts
If a user set budget/radius and price/coordinates are absent, the item is privately Unverified and no Offer is sent. If the user did not set that constraint, the same absent optional field does not block a match.
