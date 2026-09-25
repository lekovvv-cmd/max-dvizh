"""MAX's authenticated incoming webhook; network delivery stays in the outbox worker."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession
from app.api.routes.dvizh import ConfirmationIn, confirm
from app.core.config import settings
from app.db.models import Group, MaxWebhookEvent, OutboxNotification, User
from app.modules.max_integration.client import DVIZH_MESSAGE_KINDS

router = APIRouter(tags=["max integration"])


def retry_notifications_after_bot_start(session: DbSession, user_id: str) -> None:
    """Restore invitations that MAX could not deliver before the bot was started.

    A ``startapp`` deep link opens a Mini App without necessarily starting the
    bot dialog. MAX can reject a direct message in that state.  The outbox keeps
    the terminal 4xx result for observability, then this confirmed ``bot_started``
    event makes the still-relevant invitation eligible for one fresh delivery.
    The dispatcher performs the final staleness check before sending it.
    """
    for notification in session.scalars(
        select(OutboxNotification).where(
            OutboxNotification.user_id == user_id,
            OutboxNotification.kind.in_(DVIZH_MESSAGE_KINDS),
            OutboxNotification.status == "FAILED",
        )
    ):
        notification.status = "PENDING"
        notification.attempts = 0
        notification.next_attempt_at = None
        notification.locked_at = None


class MaxUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    update_type: str
    timestamp: int
    user: dict[str, object] | None = None
    chat_id: int | None = None
    callback: dict[str, object] | None = None
    payload: str | None = None


def fingerprint(update: MaxUpdate) -> str:
    callback_id = (update.callback or {}).get("callback_id")
    if callback_id:
        return "callback:" + hashlib.sha256(str(callback_id).encode()).hexdigest()
    canonical = json.dumps(update.model_dump(), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@router.post("/integrations/max/webhook")
async def max_webhook(
    request: Request, session: DbSession, x_max_bot_api_secret: str | None = Header(default=None)
) -> dict[str, bool]:
    if (
        not settings.max_webhook_secret
        or not x_max_bot_api_secret
        or not hmac.compare_digest(x_max_bot_api_secret, settings.max_webhook_secret)
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    update = MaxUpdate.model_validate(await request.json())
    key = fingerprint(update)
    if session.get(MaxWebhookEvent, key):
        return {"ok": True}
    if update.update_type == "bot_removed" and update.chat_id is not None:
        group = session.scalar(select(Group).where(Group.max_chat_id == str(update.chat_id)))
        if group:
            group.max_chat_id = None
    if update.update_type in {"bot_started", "message_callback"}:
        actor = (
            (update.callback or {}).get("user")
            if update.update_type == "message_callback"
            else update.user
        )
        if not isinstance(actor, dict):
            raise HTTPException(status_code=422, detail="Missing MAX user")
        max_user_id = str(actor.get("user_id") or "")
        if not max_user_id:
            raise HTTPException(status_code=422, detail="Missing MAX user")
        user = session.scalar(select(User).where(User.max_user_id == max_user_id))
        if user is None:
            name = str(actor.get("first_name") or actor.get("name") or "Участник")
            user = User(max_user_id=max_user_id, display_name=name[:120])
            session.add(user)
            session.flush()
        if update.update_type == "bot_started":
            retry_notifications_after_bot_start(session, user.id)
            if (
                session.scalar(
                    select(OutboxNotification.id).where(
                        OutboxNotification.dedupe_key == f"MAX_WELCOME:{user.id}"
                    )
                )
                is None
            ):
                session.add(
                    OutboxNotification(
                        kind="MAX_WELCOME",
                        user_id=user.id,
                        payload={},
                        dedupe_key=f"MAX_WELCOME:{user.id}",
                        status="PENDING",
                    )
                )
        else:
            callback = update.callback or {}
            callback_id = str(callback.get("callback_id") or "")
            payload = str(callback.get("payload") or "")
            answer = "Открой ДВИЖ, чтобы продолжить."
            parts = payload.split(":")
            if callback_id and len(parts) == 3 and parts[0] == "confirm" and all(parts[1:]):
                try:
                    result = confirm(parts[1], ConfirmationIn(candidate_id=parts[2]), session, user)
                    answer = (
                        "Ты в деле!"
                        if result["my_confirmation"] == "CONFIRMED"
                        else "Ты в листе ожидания. Проверь позже в ДВИЖе."
                    )
                except HTTPException:
                    answer = "Этот вариант уже недоступен. Открой ДВИЖ."
            if callback_id:
                session.add(
                    OutboxNotification(
                        kind="MAX_CALLBACK_ANSWER",
                        user_id=user.id,
                        payload={"callback_id": callback_id, "text": answer},
                        dedupe_key=f"MAX_CALLBACK_ANSWER:{callback_id}",
                        status="PENDING",
                    )
                )
    session.add(MaxWebhookEvent(fingerprint=key))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return {"ok": True}
