"""One-shot Dvizh notification scheduling over the existing outbox."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    DvizhCandidate,
    DvizhConfirmation,
    DvizhReaction,
    DvizhSession,
    OutboxNotification,
)
from app.modules.leisure.provider import KudaGoProvider
from app.modules.matching.dvizh import (
    active,
    aware,
    cancel_unavailable_gathered,
    enqueue,
    premeet_due_time,
)

REVIEW_REMINDER_DELAY = timedelta(minutes=30)
MATCH_REMINDER_DELAY = timedelta(minutes=15)
PREMEET_REMINDER_DELAY = timedelta(minutes=30)
SEND_BUFFER = timedelta(minutes=10)


def source_available(candidate: DvizhCandidate) -> bool | None:
    if candidate.provider != "KUDAGO":
        return None
    return KudaGoProvider().item_available(
        candidate.item_type,
        candidate.provider_item_id,
        aware(candidate.starts_at),
        aware(candidate.ends_at),
    )


def _sent_originals(session: Session, kind: str, dvizh_id: str) -> list[OutboxNotification]:
    return list(
        session.scalars(
            select(OutboxNotification).where(
                OutboxNotification.kind == kind,
                OutboxNotification.status == "SENT",
                OutboxNotification.sent_at.is_not(None),
                OutboxNotification.dedupe_key.like(f"{kind}:{dvizh_id}:%"),
            )
        )
    )


def schedule_review_reminders(session: Session, dvizh: DvizhSession, current: datetime) -> None:
    if dvizh.status not in {"CHOOSING_CANDIDATES", "COLLECTING_REACTIONS", "AWAITING_CONFIRMATION"}:
        return
    options = list(
        session.scalars(
            select(DvizhCandidate).where(
                DvizhCandidate.session_id == dvizh.id,
                DvizhCandidate.seed.is_(dvizh.status != "CHOOSING_CANDIDATES"),
            )
        )
    )
    if not options or max(aware(item.expires_at) for item in options) <= current + SEND_BUFFER:
        return
    kind = (
        "DVIZH_INITIATOR_REVIEW"
        if dvizh.status == "CHOOSING_CANDIDATES"
        else "DVIZH_REVIEW_REQUIRED"
    )
    for original in _sent_originals(session, kind, dvizh.id):
        if original.sent_at is None or aware(original.sent_at) + REVIEW_REMINDER_DELAY > current:
            continue
        if session.scalar(
            select(DvizhReaction.id)
            .join(DvizhCandidate, DvizhCandidate.id == DvizhReaction.candidate_id)
            .where(
                DvizhCandidate.session_id == dvizh.id,
                DvizhCandidate.seed.is_(dvizh.status != "CHOOSING_CANDIDATES"),
                DvizhReaction.user_id == original.user_id,
            )
        ):
            continue
        reminder = f"{kind}_REMINDER"
        enqueue(session, reminder, original.user_id, dvizh)


def schedule_match_reminders(session: Session, dvizh: DvizhSession, current: datetime) -> None:
    if dvizh.status != "AWAITING_CONFIRMATION":
        return
    candidate = active(session, dvizh)
    if candidate is None or aware(candidate.expires_at) <= current + SEND_BUFFER:
        return
    for original in _sent_originals(session, "DVIZH_MATCH_FOUND", dvizh.id):
        if (
            original.payload.get("candidate_id") != candidate.id
            or original.sent_at is None
            or aware(original.sent_at) + MATCH_REMINDER_DELAY > current
        ):
            continue
        if session.scalar(
            select(DvizhConfirmation.id).where(
                DvizhConfirmation.candidate_id == candidate.id,
                DvizhConfirmation.user_id == original.user_id,
            )
        ):
            continue
        enqueue(session, "DVIZH_MATCH_REMINDER", original.user_id, dvizh, candidate)


def schedule_premeet_reminders(session: Session, dvizh: DvizhSession, current: datetime) -> None:
    if dvizh.status != "GATHERED":
        return
    candidate = active(session, dvizh)
    if candidate is None or aware(candidate.starts_at) <= current + timedelta(minutes=1):
        return
    for original in _sent_originals(session, "DVIZH_PREMEET_CHECK", dvizh.id):
        if (
            original.payload.get("candidate_id") != candidate.id
            or original.sent_at is None
            or aware(original.sent_at)
            + min(
                PREMEET_REMINDER_DELAY,
                (aware(candidate.starts_at) - aware(original.sent_at)) / 2,
            )
            > current
        ):
            continue
        confirmation = session.scalar(
            select(DvizhConfirmation).where(
                DvizhConfirmation.candidate_id == candidate.id,
                DvizhConfirmation.user_id == original.user_id,
                DvizhConfirmation.status == "CONFIRMED",
            )
        )
        if confirmation and confirmation.reconfirmed_at is None:
            enqueue(session, "DVIZH_PREMEET_REMINDER", original.user_id, dvizh, candidate)


def process_gathered(session: Session, current: datetime) -> None:
    """Check a gathered source before sending the timed second question."""
    ids = list(session.scalars(select(DvizhSession.id).where(DvizhSession.status == "GATHERED")))
    session.commit()
    for dvizh_id in ids:
        dvizh = session.scalar(
            select(DvizhSession).where(DvizhSession.id == dvizh_id).with_for_update()
        )
        if dvizh is None or dvizh.status != "GATHERED":
            session.commit()
            continue
        candidate = active(session, dvizh)
        if candidate is None or aware(candidate.starts_at) <= current:
            session.commit()
            continue
        if dvizh.premeet_due_at is None:
            # Older gathered rows predate the scheduling column. Do not infer
            # their historic gathering time from a different timestamp.
            dvizh.premeet_due_at = premeet_due_time(candidate.starts_at, current)
        due = aware(dvizh.premeet_due_at)
        if due > current:
            session.commit()
            continue
        already_checked = session.scalar(
            select(OutboxNotification.id).where(
                OutboxNotification.kind == "DVIZH_PREMEET_CHECK",
                OutboxNotification.dedupe_key.like(
                    f"DVIZH_PREMEET_CHECK:{dvizh.id}:{candidate.id}:%"
                ),
            )
        )
        final_check_due = aware(candidate.starts_at) <= current + timedelta(hours=2)
        needs_source_check = not already_checked or (
            final_check_due and dvizh.source_rechecked_at is None
        )
        session.commit()
        availability = source_available(candidate) if needs_source_check else None
        dvizh = session.scalar(
            select(DvizhSession)
            .where(DvizhSession.id == dvizh_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if dvizh is None or dvizh.status != "GATHERED" or dvizh.active_candidate_id != candidate.id:
            session.commit()
            continue
        if final_check_due and needs_source_check:
            dvizh.source_rechecked_at = current
        if availability is False:
            cancel_unavailable_gathered(session, dvizh, candidate)
            session.commit()
            continue
        for confirmation in session.scalars(
            select(DvizhConfirmation).where(
                DvizhConfirmation.candidate_id == candidate.id,
                DvizhConfirmation.status == "CONFIRMED",
                DvizhConfirmation.reconfirmed_at.is_(None),
            )
        ):
            enqueue(session, "DVIZH_PREMEET_CHECK", confirmation.user_id, dvizh, candidate)
        schedule_premeet_reminders(session, dvizh, current)
        session.commit()
