"""MAX Bot API boundary. It sends only after a real token is configured."""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import OutboxNotification, User


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


def dispatch_pending(session: Session) -> int:
    """Best-effort outbox dispatch; failures remain queued for the next worker run."""
    if not settings.max_bot_token:
        return 0
    delivered = 0
    for event in session.scalars(
        select(OutboxNotification).where(OutboxNotification.status == "PENDING").limit(50)
    ):
        user = session.get(User, event.user_id)
        if user is None:
            event.status = "FAILED"
            continue
        title = str(event.payload.get("title") or "Новое предложение в ДВИЖ")
        text = (
            f"⚡ ДВИЖ СОБРАЛСЯ: {title}"
            if event.kind == "CONFIRMED_PLAN"
            else "В ДВИЖ появилось новое личное предложение"
        )
        try:
            send_bot_message(user.max_user_id, text)
            event.status = "SENT"
            delivered += 1
        except httpx.HTTPError:
            event.attempts += 1
    session.commit()
    return delivered
