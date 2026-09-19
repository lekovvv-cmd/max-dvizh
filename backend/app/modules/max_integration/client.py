"""MAX Bot boundary and database-coordinated outbox dispatcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezones import display_timezone
from app.db.models import OutboxNotification, User


def utcnow() -> datetime:
    return datetime.now(UTC)


def send_bot_message(max_user_id: str, text: str) -> bool:
    if not settings.max_bot_token:
        return False
    response = httpx.post(
        f"{settings.max_bot_api_base}/messages",
        params={"user_id": max_user_id},
        headers={"Authorization": settings.max_bot_token},
        json={"text": text, "format": "markdown"},
        timeout=5,
    )
    response.raise_for_status()
    return True


def _text(event: OutboxNotification) -> str:
    title = str(event.payload.get("title") or "ДВИЖ")
    group = str(event.payload.get("group_name") or "Компания")
    try:
        start = datetime.fromisoformat(str(event.payload["starts_at"]))
        zone = display_timezone(str(event.payload.get("timezone") or "UTC"))
        when = start.astimezone(zone).strftime("%d.%m в %H:%M")
    except (KeyError, ValueError):
        when = "скоро"
    kind = "plan" if event.kind == "CONFIRMED_PLAN" else "offer"
    identifier = event.payload.get("plan_id" if kind == "plan" else "offer_id")
    link = (
        f"\nhttps://max.ru/{settings.max_bot_username}?startapp={kind}_{identifier}"
        if settings.max_bot_username and identifier
        else ""
    )
    heading = "⚡ ДВИЖ СОБРАЛСЯ" if kind == "plan" else "🎮 Новый ДВИЖ"
    return f"{heading}\n{title} · {when}\n{group}{link}"


def dispatch_pending(session: Session, batch_size: int = 50) -> int:
    """Claim rows using ``FOR UPDATE SKIP LOCKED`` then deliver outside the lock.

    A claim is committed before network I/O, so concurrent worker processes do
    not send the same pending row. A stale PROCESSING claim is retried after a
    bounded lease; external HTTP cannot provide absolute exactly-once delivery.
    """
    if not settings.max_bot_token:
        return 0
    current = utcnow()
    stale_before = current - timedelta(minutes=5)
    for event in session.scalars(
        select(OutboxNotification)
        .where(
            OutboxNotification.status == "PROCESSING", OutboxNotification.locked_at < stale_before
        )
        .with_for_update(skip_locked=True)
    ):
        event.status = "PENDING"
        event.locked_at = None
    session.commit()
    claimed = list(
        session.scalars(
            select(OutboxNotification)
            .where(
                OutboxNotification.status == "PENDING",
                or_(
                    OutboxNotification.next_attempt_at.is_(None),
                    OutboxNotification.next_attempt_at <= current,
                ),
            )
            .order_by(OutboxNotification.created_at, OutboxNotification.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    for event in claimed:
        event.status = "PROCESSING"
        event.locked_at = current
    session.commit()

    delivered = 0
    for claimed_event in claimed:
        current_event = session.get(OutboxNotification, claimed_event.id)
        if current_event is None or current_event.status != "PROCESSING":
            continue
        event = current_event
        user = session.get(User, event.user_id)
        if user is None:
            event.status = "FAILED"
            event.locked_at = None
            session.commit()
            continue
        try:
            send_bot_message(user.max_user_id, _text(event))
        except httpx.HTTPError:
            event.attempts += 1
            event.status = "PENDING"
            event.locked_at = None
            delay = min(2 ** min(event.attempts, 8), settings.outbox_retry_max_seconds)
            event.next_attempt_at = utcnow() + timedelta(seconds=delay)
            session.commit()
        else:
            event.status = "SENT"
            event.locked_at = None
            event.next_attempt_at = None
            session.commit()
            delivered += 1
    return delivered
