# 03 — State machines

## Intent

```text
ACTIVE
├─ pause → PAUSED
├─ one-time ttl → EXPIRED
└─ cancel → CANCELLED

PAUSED
└─ resume → ACTIVE
```

Recurring intent remains active across occurrences until paused/cancelled.

## CandidatePlan

```text
COLLECTING
├─ enough valid accepted users → CONFIRMED_OPEN
├─ source/time invalid → CANCELLED
└─ ttl ends → EXPIRED

CONFIRMED_OPEN
├─ reaches effective capacity → CONFIRMED
├─ joining cutoff → CONFIRMED
└─ accepted cancellation below minimum → COLLECTING

CONFIRMED
└─ accepted cancellation below minimum before cutoff → COLLECTING
```

## Offer

A CandidatePlan may be created only after at least one Exact or Near eligible user exists. Unverified provider items alone do not produce a CandidatePlan or persisted source snapshot.

```text
PENDING
├─ accept while personal minimum unmet → WAITING_CONDITION
├─ accept with sufficient valid count → ACCEPTED
├─ exact N already full → WAITLISTED
├─ reject → REJECTED
├─ ttl ends → EXPIRED
└─ candidate/user conflict changes → INVALIDATED

WAITING_CONDITION → ACCEPTED when a valid accepted set satisfies every personal range
ACCEPTED → WAITING_CONDITION if cancellation or a changed constraint breaks the valid set before cutoff
WAITLISTED → WAITING_CONDITION / ACCEPTED when an admitted place opens
WAITING_CONDITION / ACCEPTED / WAITLISTED → CANCELLED_BY_USER before cutoff
```

## Accept Offer transaction

1. Lock the current User, then CandidatePlan, then Offer; re-read their state inside the transaction.
2. Require Offer=PENDING.
3. Recheck candidate/source validity.
4. Recheck user's overlapping accepted/confirmed plans.
5. Recompute stale constraints as needed.
6. If Near, require explicit exception confirmation.
7. Record the response; admit within capacity or privately waitlist for exact N.
8. Invalidate/recompute overlapping pending Offers for user; all other pending Offers remain in the user's global pool.
9. Recompute CandidatePlan and affected overlapping CandidatePlans from persisted source snapshots; no new provider call is needed.
10. If all accepted constraints fit, mark CONFIRMED_OPEN at minimum; keep joining until capacity/cutoff.
11. Queue outbound MAX notification/share task.

## Reject Offer

Mark REJECTED and recompute from the source snapshot. The plan remains available to other eligible members. Never reveal rejection identity to others.

## Near

Near user does not count while pending.

Example: budget 300, plan 400, allowed Near → explicit +100 confirmation → accepted.

## Overlap example

Bowling 20:00–22:00 + PC Club 20:00–23:00 can both be shown. If user accepts PC Club, Bowling Offer is invalidated/recomputed. Bowling may continue with others.

## Independent plans
Plans without shared time/user conflict may proceed simultaneously.

## Post-confirm changes
Prefer a simple documented MVP policy. Do not fake a robust rescheduling/cancellation engine if not implemented end-to-end.
