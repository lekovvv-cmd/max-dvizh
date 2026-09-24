"""MAX Bot boundary and database-coordinated outbox dispatcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezones import display_timezone
from app.db.models import DvizhCandidate, DvizhSession, GroupMember, OutboxNotification, User


def utcnow() -> datetime:
    return datetime.now(UTC)


def _dvizh_notification_current(session: Session, event: OutboxNotification) -> bool:
    if not event.kind.startswith("DVIZH_"):
        return True
    dvizh_id = event.payload.get("dvizh_id")
    if not isinstance(dvizh_id, str):
        return False
    dvizh = session.get(DvizhSession, dvizh_id)
    if dvizh is None:
        return False
    if event.kind == "DVIZH_SOURCE_CANCELLED":
        return dvizh.status == "CANCELLED"
    if (
        session.scalar(
            select(GroupMember.id).where(
                GroupMember.group_id == dvizh.group_id, GroupMember.user_id == event.user_id
            )
        )
        is None
    ):
        return False
    deadline = dvizh.expires_at if dvizh.expires_at.tzinfo else dvizh.expires_at.replace(tzinfo=UTC)
    if deadline <= utcnow() and dvizh.status != "GATHERED":
        return False
    if event.kind == "DVIZH_INITIATOR_REVIEW":
        if dvizh.status != "CHOOSING_CANDIDATES":
            return False
        require_seed = False
    elif event.kind == "DVIZH_REVIEW_REQUIRED":
        if dvizh.status not in {"COLLECTING_REACTIONS", "AWAITING_CONFIRMATION"}:
            return False
        require_seed = True
    else:
        require_seed = None
    if require_seed is not None:
        for option in session.scalars(
            select(DvizhCandidate).where(DvizhCandidate.session_id == dvizh.id)
        ):
            expiry = (
                option.expires_at
                if option.expires_at.tzinfo
                else option.expires_at.replace(tzinfo=UTC)
            )
            if expiry > utcnow() and (not require_seed or option.seed):
                return True
        return False
    candidate_id = event.payload.get("candidate_id")
    if not isinstance(candidate_id, str) or dvizh.active_candidate_id != candidate_id:
        return False
    candidate = session.get(DvizhCandidate, candidate_id)
    if candidate is None or candidate.session_id != dvizh.id:
        return False
    expiry = (
        candidate.expires_at
        if candidate.expires_at.tzinfo
        else candidate.expires_at.replace(tzinfo=UTC)
    )
    if event.kind == "DVIZH_MATCH_FOUND":
        return dvizh.status == "AWAITING_CONFIRMATION" and expiry > utcnow()
    if event.kind == "DVIZH_GATHERED":
        return dvizh.status == "GATHERED"
    return False


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


def send_welcome(max_user_id: str) -> None:
    text = "ДВИЖ собирает компанию без бесконечных «ну что, идём?». Подай сигнал — я напишу, когда понадобится твой выбор."
    link = (
        f"https://max.ru/{settings.max_bot_username}?startapp"
        if settings.max_bot_username
        else settings.max_mini_app_url
    )
    body: dict[str, object] = {"text": text}
    if link:
        body["attachments"] = [
            {
                "type": "inline_keyboard",
                "payload": {"buttons": [[{"type": "link", "text": "Открыть ДВИЖ", "url": link}]]},
            }
        ]
    response = httpx.post(
        f"{settings.max_bot_api_base}/messages",
        params={"user_id": max_user_id},
        headers={"Authorization": settings.max_bot_token},
        json=body,
        timeout=5,
    )
    response.raise_for_status()


def dvizh_link(dvizh_id: str) -> str | None:
    return (
        f"https://max.ru/{settings.max_bot_username}?startapp=dvizh_{dvizh_id}"
        if settings.max_bot_username
        else None
    )


def _dvizh_message(event: OutboxNotification) -> tuple[str, str, str | None]:
    dvizh_id = str(event.payload.get("dvizh_id") or "")
    activities = event.payload.get("activity_ids")
    from app.modules.leisure.taxonomy import BY_ID

    label = (
        " или ".join(BY_ID[a].label for a in activities if a in BY_ID)
        if isinstance(activities, list)
        else "Досуг"
    )
    title = str(event.payload.get("title") or label or "Движ")
    if event.kind == "DVIZH_INITIATOR_REVIEW":
        return (
            f"Нашли варианты для твоего регулярного сигнала\n{label}\nВыбери, куда ты пошёл бы, и запусти движ.",
            "Выбрать варианты",
            dvizh_link(dvizh_id),
        )
    if event.kind == "DVIZH_REVIEW_REQUIRED":
        return (
            f"🎯 В компании намечается движ\n{label}\nЕсть подходящие варианты. Отметь, куда ты реально пошёл бы.",
            "Выбрать варианты",
            dvizh_link(dvizh_id),
        )
    if event.kind == "DVIZH_MATCH_FOUND":
        return (
            f"👀 Похоже, совпало\n{title}\nЭтот вариант выбрали достаточно людей. Осталось подтвердить участие.",
            "Я в деле",
            dvizh_link(dvizh_id),
        )
    if event.kind == "DVIZH_SOURCE_CANCELLED":
        return (
            f"Место больше недоступно\n{title}\nПроверь движ и подай новый сигнал, если хочешь собрать компанию.",
            "Открыть движ",
            dvizh_link(dvizh_id),
        )
    return (
        f"⚡ ДВИЖ СОБРАЛСЯ\n{title}\nНужное число участников подтвердило.",
        "Открыть движ",
        dvizh_link(dvizh_id),
    )


def send_dvizh_message(max_user_id: str, event: OutboxNotification) -> bool:
    text, label, link = _dvizh_message(event)
    body: dict[str, object] = {"text": text}
    if link:
        button: dict[str, str] = {"type": "link", "text": label, "url": link}
        if event.kind == "DVIZH_MATCH_FOUND" and event.payload.get("compatibility") == "EXACT":
            button = {
                "type": "callback",
                "text": "Я в деле",
                "payload": f"confirm:{event.payload['dvizh_id']}:{event.payload['candidate_id']}",
            }
        body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": [[button]]}}]
    response = httpx.post(
        f"{settings.max_bot_api_base}/messages",
        params={"user_id": max_user_id},
        headers={"Authorization": settings.max_bot_token},
        json=body,
        timeout=5,
    )
    response.raise_for_status()
    return True


def send_callback_answer(callback_id: str, message: str) -> None:
    response = httpx.post(
        f"{settings.max_bot_api_base}/answers",
        params={"callback_id": callback_id},
        headers={"Authorization": settings.max_bot_token},
        json={"notification": message},
        timeout=5,
    )
    response.raise_for_status()
    if response.json().get("success") is not True:
        raise httpx.HTTPStatusError(
            "MAX rejected the callback answer", request=response.request, response=response
        )


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
        if not _dvizh_notification_current(session, event):
            event.status = "CANCELLED"
            event.locked_at = None
            session.commit()
            continue
        user = session.get(User, event.user_id)
        if user is None:
            event.status = "FAILED"
            event.locked_at = None
            session.commit()
            continue
        try:
            if event.kind in {
                "DVIZH_INITIATOR_REVIEW",
                "DVIZH_REVIEW_REQUIRED",
                "DVIZH_MATCH_FOUND",
                "DVIZH_GATHERED",
                "DVIZH_SOURCE_CANCELLED",
            }:
                send_dvizh_message(user.max_user_id, event)
            elif event.kind == "MAX_CALLBACK_ANSWER":
                send_callback_answer(str(event.payload["callback_id"]), str(event.payload["text"]))
            elif event.kind == "MAX_WELCOME":
                send_welcome(user.max_user_id)
            else:
                send_bot_message(user.max_user_id, _text(event))
        except httpx.HTTPError as error:
            event.attempts += 1
            response_code = (
                error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
            )
            terminal = (
                response_code is not None and 400 <= response_code < 500 and response_code != 429
            )
            event.status = "FAILED" if terminal or event.attempts >= 8 else "PENDING"
            event.locked_at = None
            if event.status == "PENDING":
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
