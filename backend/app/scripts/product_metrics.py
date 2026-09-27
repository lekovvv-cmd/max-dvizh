"""Read-only product timing report. Run with the API's DATABASE_URL."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import (
    DvizhCandidate,
    DvizhConfirmation,
    DvizhReaction,
    DvizhSession,
    Intent,
    OutboxNotification,
)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def timestamp(value: datetime | None) -> str:
    return aware(value).astimezone(UTC).isoformat() if value else "n/a"


def elapsed(start: datetime | None, end: datetime | None) -> float | str:
    if start is None or end is None or aware(end) < aware(start):
        return "n/a"
    return round((aware(end) - aware(start)).total_seconds(), 3)


def metrics_for(session: Session, dvizh: DvizhSession) -> dict[str, object]:
    signal_created = session.scalar(select(Intent.created_at).where(Intent.id == dvizh.signal_id))
    first_reaction = session.scalar(
        select(func.min(DvizhReaction.created_at))
        .join(DvizhCandidate, DvizhCandidate.id == DvizhReaction.candidate_id)
        .where(DvizhCandidate.session_id == dvizh.id, DvizhReaction.user_id != dvizh.initiator_id)
    )
    notification = (
        select(OutboxNotification)
        .where(OutboxNotification.payload["dvizh_id"].as_string() == dvizh.id)
        .subquery()
    )

    def event_time(kind: str) -> datetime | None:
        value = session.scalar(
            select(func.min(notification.c.created_at)).where(notification.c.kind == kind)
        )
        return value if isinstance(value, datetime) else None

    match_found = event_time("DVIZH_MATCH_FOUND")
    gathered = event_time("DVIZH_GATHERED")
    sent_reviews = (
        notification.c.kind == "DVIZH_REVIEW_REQUIRED",
        notification.c.status == "SENT",
    )
    review_sent = session.scalar(select(func.min(notification.c.sent_at)).where(*sent_reviews))
    review_count = (
        session.scalar(select(func.count()).select_from(notification).where(*sent_reviews)) or 0
    )
    final_confirmation = session.scalar(
        select(func.min(DvizhConfirmation.confirmed_at))
        .join(DvizhCandidate, DvizhCandidate.id == DvizhConfirmation.candidate_id)
        .where(DvizhCandidate.session_id == dvizh.id)
    )
    confirmation_count = (
        session.scalar(
            select(func.count())
            .select_from(DvizhConfirmation)
            .where(
                DvizhConfirmation.candidate_id == dvizh.active_candidate_id,
                DvizhConfirmation.status == "CONFIRMED",
            )
        )
        or 0
    )
    return {
        "dvizh_id": dvizh.id,
        "events": {
            "signal_created": timestamp(signal_created),
            "dvizh_launched": timestamp(dvizh.launched_at),
            "review_notification_sent": timestamp(review_sent),
            "first_reaction": timestamp(first_reaction),
            "match_found": timestamp(match_found),
            "final_confirmation": timestamp(final_confirmation),
            "dvizh_gathered": timestamp(gathered),
        },
        "seconds_from_launch_to_first_reaction": elapsed(dvizh.launched_at, first_reaction),
        "seconds_from_launch_to_match": elapsed(dvizh.launched_at, match_found),
        "seconds_from_launch_to_gathered": elapsed(dvizh.launched_at, gathered),
        "number_of_review_notifications": review_count,
        "number_of_confirmations": confirmation_count,
        "manual_messages_by_initiator_after_launch": {
            "value": 0,
            "basis": "product property: notifications are automatic; real messages are not measured",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dvizh-id", help="Report one Dvizh; otherwise the latest 20")
    args = parser.parse_args()
    from app.db.session import SessionLocal

    query = select(DvizhSession).order_by(DvizhSession.created_at.desc(), DvizhSession.id)
    if args.dvizh_id:
        query = query.where(DvizhSession.id == args.dvizh_id)
    try:
        with SessionLocal() as session:
            reports = [metrics_for(session, dvizh) for dvizh in session.scalars(query.limit(20))]
    except SQLAlchemyError:
        print("metrics_failed: check DATABASE_URL and migrations; database details omitted")
        return 1
    if not reports:
        print("n/a: no Dvizh records found")
        return 0
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
