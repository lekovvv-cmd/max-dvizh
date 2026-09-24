"""One-company Dvizh state machine; soft reactions never count as confirmations."""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezones import display_timezone
from app.db.models import (
    CandidatePlan,
    DvizhCandidate,
    DvizhConfirmation,
    DvizhReaction,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    Location,
    Offer,
    OutboxNotification,
    User,
)
from app.modules.leisure.provider import NormalizedLeisureItem
from app.modules.leisure.taxonomy import expand
from app.modules.matching.domain import compatibility, contains_interval, haversine_km, overlaps


def now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def fail(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def member(session: Session, group_id: str, user_id: str) -> bool:
    return (
        session.scalar(
            select(GroupMember.id).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        )
        is not None
    )


def launched(session: Session, dvizh_id: str) -> bool:
    return (
        session.scalar(
            select(DvizhCandidate.id).where(
                DvizhCandidate.session_id == dvizh_id, DvizhCandidate.seed.is_(True)
            )
        )
        is not None
    )


def get_dvizh(session: Session, dvizh_id: str, user_id: str, *, lock: bool = False) -> DvizhSession:
    query = select(DvizhSession).where(DvizhSession.id == dvizh_id)
    if lock:
        query = query.with_for_update()
    dvizh = session.scalar(query)
    if dvizh is None or not member(session, dvizh.group_id, user_id):
        raise fail(404, "Движ не найден")
    if dvizh.initiator_id != user_id and not launched(session, dvizh.id):
        raise fail(404, "Движ не найден")
    return dvizh


def candidates(session: Session, dvizh_id: str) -> list[DvizhCandidate]:
    return list(
        session.scalars(
            select(DvizhCandidate)
            .where(DvizhCandidate.session_id == dvizh_id)
            .order_by(DvizhCandidate.position, DvizhCandidate.id)
        )
    )


def active(session: Session, dvizh: DvizhSession) -> DvizhCandidate | None:
    return (
        session.get(DvizhCandidate, dvizh.active_candidate_id)
        if dvizh.active_candidate_id
        else None
    )


def conflict(session: Session, user_id: str, candidate: DvizhCandidate) -> bool:
    for offer in session.scalars(
        select(Offer).where(Offer.user_id == user_id, Offer.status == "ACCEPTED")
    ):
        plan = session.get(CandidatePlan, offer.candidate_plan_id)
        if plan and overlaps(candidate.starts_at, candidate.ends_at, plan.starts_at, plan.ends_at):
            return True
    for confirmation in session.scalars(
        select(DvizhConfirmation).where(
            DvizhConfirmation.user_id == user_id, DvizhConfirmation.status == "CONFIRMED"
        )
    ):
        other = session.get(DvizhCandidate, confirmation.candidate_id)
        other_session = session.get(DvizhSession, other.session_id) if other else None
        if (
            other
            and other_session
            and other_session.status == "GATHERED"
            and other.session_id != candidate.session_id
            and overlaps(candidate.starts_at, candidate.ends_at, other.starts_at, other.ends_at)
        ):
            return True
    return False


def enqueue(
    session: Session,
    kind: str,
    user_id: str,
    dvizh: DvizhSession,
    candidate: DvizhCandidate | None = None,
) -> None:
    key = f"{kind}:{dvizh.id}:{candidate.id if candidate else 'review'}:{user_id}"
    if session.scalar(select(OutboxNotification.id).where(OutboxNotification.dedupe_key == key)):
        return
    group = session.get(Group, dvizh.group_id)
    payload: dict[str, object] = {
        "dvizh_id": dvizh.id,
        "group_name": group.name if group else "Компания",
        "activity_ids": dvizh.activity_ids,
    }
    if candidate:
        payload.update(
            {
                "candidate_id": candidate.id,
                "title": candidate.title,
                "starts_at": candidate.starts_at.isoformat(),
                "timezone": group.timezone_name if group else "UTC",
                "compatibility": candidate.compatibility,
            }
        )
    session.add(
        OutboxNotification(
            kind=kind, user_id=user_id, payload=payload, dedupe_key=key, status="PENDING"
        )
    )


_WEEKDAYS = {day: index for index, day in enumerate(("пн", "вт", "ср", "чт", "пт", "сб", "вс"))}
_DAY = r"(?:пн|вт|ср|чт|пт|сб|вс)"
_DAY_GROUP = rf"{_DAY}(?:\s*[–—-]\s*{_DAY})?(?:\s*,\s*{_DAY}(?:\s*[–—-]\s*{_DAY})?)*"
_HOURS_ENTRY = re.compile(
    rf"(?P<days>ежедневно|{_DAY_GROUP})\s+"
    r"(?P<open_h>\d{1,2}):(?P<open_m>\d{2})\s*[–—-]\s*"
    r"(?P<close_h>\d{1,2}):(?P<close_m>\d{2})",
    re.I,
)


def _schedule_days(value: str) -> set[int]:
    if value == "ежедневно":
        return set(range(7))
    days: set[int] = set()
    for part in value.split(","):
        endpoints = re.split(r"\s*[–—-]\s*", part.strip())
        if any(day not in _WEEKDAYS for day in endpoints):
            return set()
        first = _WEEKDAYS[endpoints[0]]
        last = _WEEKDAYS[endpoints[-1]]
        days.update(index % 7 for index in range(first, first + (last - first) % 7 + 1))
    return days


def _daily_hours_fit(
    timetable: str | None, start: datetime, end: datetime, timezone_name: str | None
) -> bool:
    """Accept only a fully parsed provider schedule covering the entire visit."""
    if not timetable:
        return False
    zone = display_timezone(timezone_name)
    local_start, local_end = start.astimezone(zone), end.astimezone(zone)
    entries: list[tuple[set[int], int, int]] = []
    cursor = 0
    for match in _HOURS_ENTRY.finditer(timetable.casefold()):
        if timetable[cursor : match.start()].strip(" ,;\n"):
            return False
        opening = int(match["open_h"]) * 60 + int(match["open_m"])
        closing = int(match["close_h"]) * 60 + int(match["close_m"])
        if opening >= 24 * 60 or closing > 24 * 60 or not _schedule_days(match["days"]):
            return False
        entries.append((_schedule_days(match["days"]), opening, closing))
        cursor = match.end()
    if not entries or timetable[cursor:].strip(" ,;\n"):
        return False
    for offset in (-1, 0):
        day = local_start.date() + timedelta(days=offset)
        for days, opening, closing in entries:
            if day.weekday() not in days:
                continue
            opened = datetime.combine(day, time.min, zone) + timedelta(minutes=opening)
            closed = datetime.combine(day, time.min, zone) + timedelta(
                minutes=closing + (24 * 60 if closing <= opening else 0)
            )
            if opened <= local_start and local_end <= closed:
                return True
    return False


def build_candidate(
    intent: Intent,
    dvizh: DvizhSession,
    item: NormalizedLeisureItem,
    position: int,
    location: Location | None,
    timezone_name: str | None,
) -> DvizhCandidate | None:
    if not set(item.categories).intersection(
        expand(dvizh.activity_ids)
    ) or item.classification_confidence not in {"HIGH", "MEDIUM"}:
        return None
    start, end = item.starts_at, item.ends_at
    if item.item_type == "PLACE":
        start = (
            max(aware(intent.available_from), now() + timedelta(minutes=15))
            if intent.available_from
            else now() + timedelta(minutes=15)
        )
        start = start.replace(second=0, microsecond=0)
        end = (
            min(
                start + timedelta(minutes=settings.place_plan_duration_minutes),
                aware(intent.available_to),
            )
            if intent.available_to
            else start
        )
        if not _daily_hours_fit(item.timetable, start, end, timezone_name):
            return None
    if (
        intent.available_from is None
        or intent.available_to is None
        or not contains_interval(intent.available_from, intent.available_to, start, end)
        or end <= start
        or start <= now() + timedelta(minutes=10)
    ):
        return None
    distance = (
        haversine_km(location.latitude, location.longitude, item.latitude, item.longitude)
        if location and item.latitude is not None and item.longitude is not None
        else None
    )
    fit = compatibility(
        price=item.price_min,
        max_budget=intent.budget_max,
        near_limit=settings.near_budget_max_delta_rub,
        distance_km=distance,
        radius_km=intent.radius_km,
    )
    if fit.kind not in {"EXACT", "NEAR"}:
        return None
    return DvizhCandidate(
        session_id=dvizh.id,
        position=position,
        provider=item.provider,
        provider_item_id=item.provider_id,
        item_type=item.item_type,
        title=item.title,
        activity_ids=list(item.categories),
        venue_name=item.venue_name,
        starts_at=start,
        ends_at=end,
        price_text=item.price_text,
        price_min=item.price_min,
        distance_km=round(distance, 1) if distance is not None else None,
        budget_delta=fit.budget_delta,
        compatibility=fit.kind,
        address_text=item.address_text,
        source_url=item.source_url,
        image_url=item.image_url,
        seed=False,
        expires_at=min(start - timedelta(minutes=10), aware(dvizh.expires_at)),
    )


def add_candidates(
    session: Session, dvizh: DvizhSession, intent: Intent, items: list[NormalizedLeisureItem]
) -> int:
    location = (
        session.get(Location, intent.origin_location_id) if intent.origin_location_id else None
    )
    group = session.get(Group, dvizh.group_id)
    existing = candidates(session, dvizh.id)
    seen = {
        (c.provider, c.provider_item_id, aware(c.starts_at) if c.item_type == "EVENT" else None)
        for c in existing
    }
    seen_titles = {
        (
            re.sub(r"\W+", "", c.title.casefold()),
            re.sub(r"\W+", "", (c.address_text or c.venue_name or "").casefold()),
            aware(c.starts_at) if c.item_type == "EVENT" else None,
        )
        for c in existing
    }
    prepared: list[DvizhCandidate] = []
    for item in items:
        identity = (
            item.provider,
            item.provider_id,
            aware(item.starts_at) if item.item_type == "EVENT" else None,
        )
        if identity in seen:
            continue
        candidate = build_candidate(
            intent, dvizh, item, 0, location, group.timezone_name if group else None
        )
        if candidate:
            title_identity = (
                re.sub(r"\W+", "", candidate.title.casefold()),
                re.sub(
                    r"\W+", "", (candidate.address_text or candidate.venue_name or "").casefold()
                ),
                aware(candidate.starts_at) if candidate.item_type == "EVENT" else None,
            )
            if title_identity in seen_titles:
                continue
            seen.add(identity)
            seen_titles.add(title_identity)
            prepared.append(candidate)
    prepared.sort(
        key=lambda c: (
            c.compatibility != "EXACT",
            c.distance_km is None,
            c.distance_km or 0,
            c.starts_at,
            c.provider_item_id,
        )
    )
    for position, candidate in enumerate(prepared, start=len(existing)):
        candidate.position = position
        session.add(candidate)
    return len(prepared)


def expire(session: Session, dvizh: DvizhSession) -> None:
    if (
        dvizh.status not in {"GATHERED", "CANCELLED", "EXPIRED"}
        and aware(dvizh.expires_at) <= now()
    ):
        dvizh.status = "EXPIRED"
        signal = session.get(Intent, dvizh.signal_id)
        if signal and signal.flow_version == 2 and signal.status == "ACTIVE":
            signal.status = "EXPIRED"
    elif dvizh.status == "CHOOSING_CANDIDATES" and not any(
        aware(candidate.expires_at) > now() for candidate in candidates(session, dvizh.id)
    ):
        dvizh.status = "NO_SOURCE"


def reaction_count(session: Session, candidate_id: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(DvizhReaction)
            .join(GroupMember, GroupMember.user_id == DvizhReaction.user_id)
            .join(DvizhCandidate, DvizhCandidate.id == DvizhReaction.candidate_id)
            .join(DvizhSession, DvizhSession.id == DvizhCandidate.session_id)
            .where(
                DvizhReaction.candidate_id == candidate_id,
                DvizhReaction.value == "WOULD_GO",
                GroupMember.group_id == DvizhSession.group_id,
            )
        )
        or 0
    )


def confirmation_count(session: Session, candidate_id: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(DvizhConfirmation)
            .join(DvizhCandidate, DvizhCandidate.id == DvizhConfirmation.candidate_id)
            .join(DvizhSession, DvizhSession.id == DvizhCandidate.session_id)
            .join(GroupMember, GroupMember.user_id == DvizhConfirmation.user_id)
            .where(
                DvizhConfirmation.candidate_id == candidate_id,
                DvizhConfirmation.status == "CONFIRMED",
                GroupMember.group_id == DvizhSession.group_id,
            )
        )
        or 0
    )


def eligible_reaction_count(session: Session, candidate_id: str) -> int:
    """A final decline removes only that person's current soft reaction from matching."""
    return (
        session.scalar(
            select(func.count())
            .select_from(DvizhReaction)
            .join(GroupMember, GroupMember.user_id == DvizhReaction.user_id)
            .join(DvizhCandidate, DvizhCandidate.id == DvizhReaction.candidate_id)
            .join(DvizhSession, DvizhSession.id == DvizhCandidate.session_id)
            .outerjoin(
                DvizhConfirmation,
                (DvizhConfirmation.candidate_id == DvizhReaction.candidate_id)
                & (DvizhConfirmation.user_id == DvizhReaction.user_id)
                & (DvizhConfirmation.status == "DECLINED"),
            )
            .where(
                DvizhReaction.candidate_id == candidate_id,
                DvizhReaction.value == "WOULD_GO",
                GroupMember.group_id == DvizhSession.group_id,
                DvizhConfirmation.id.is_(None),
            )
        )
        or 0
    )


def recompute(session: Session, dvizh: DvizhSession) -> None:
    expire(session, dvizh)
    if dvizh.status not in {"COLLECTING_REACTIONS", "AWAITING_CONFIRMATION"}:
        return
    ordered = [c for c in candidates(session, dvizh.id) if c.seed and aware(c.expires_at) > now()]
    old_active = dvizh.active_candidate_id
    if not ordered:
        _supersede_confirmations(session, old_active)
        dvizh.active_candidate_id = None
        dvizh.status = "NO_MATCH"
        signal = session.get(Intent, dvizh.signal_id)
        if signal and signal.flow_version == 2 and signal.status == "ACTIVE":
            signal.status = "EXPIRED"
        return
    if dvizh.status == "AWAITING_CONFIRMATION":
        current = active(session, dvizh)
        if current and aware(current.expires_at) > now():
            if eligible_reaction_count(session, current.id) >= dvizh.min_people:
                return
    for candidate in ordered:
        if candidate.id == dvizh.active_candidate_id:
            continue
        if eligible_reaction_count(session, candidate.id) < dvizh.min_people:
            continue
        _supersede_confirmations(session, old_active)
        dvizh.active_candidate_id = candidate.id
        dvizh.status = "AWAITING_CONFIRMATION"
        session.flush()
        for reaction in session.scalars(
            select(DvizhReaction).where(
                DvizhReaction.candidate_id == candidate.id, DvizhReaction.value == "WOULD_GO"
            )
        ):
            declined = session.scalar(
                select(DvizhConfirmation.id).where(
                    DvizhConfirmation.candidate_id == candidate.id,
                    DvizhConfirmation.user_id == reaction.user_id,
                    DvizhConfirmation.status == "DECLINED",
                )
            )
            if member(session, dvizh.group_id, reaction.user_id) and not declined:
                enqueue(session, "DVIZH_MATCH_FOUND", reaction.user_id, dvizh, candidate)
        return
    _supersede_confirmations(session, old_active)
    dvizh.active_candidate_id = None
    dvizh.status = "COLLECTING_REACTIONS"


def _supersede_confirmations(session: Session, candidate_id: str | None) -> None:
    if candidate_id is None:
        return
    for confirmation in session.scalars(
        select(DvizhConfirmation).where(
            DvizhConfirmation.candidate_id == candidate_id,
            DvizhConfirmation.status.in_(("CONFIRMED", "WAITLISTED")),
        )
    ):
        confirmation.status = "SUPERSEDED"


def public_candidate(
    session: Session, candidate: DvizhCandidate, user_id: str
) -> dict[str, object]:
    reaction = session.scalar(
        select(DvizhReaction).where(
            DvizhReaction.candidate_id == candidate.id, DvizhReaction.user_id == user_id
        )
    )
    return {
        "id": candidate.id,
        "title": candidate.title,
        "venue_name": candidate.venue_name,
        "starts_at": candidate.starts_at,
        "ends_at": candidate.ends_at,
        "price_text": candidate.price_text,
        "price_min": candidate.price_min,
        "distance_km": candidate.distance_km,
        "address_text": candidate.address_text,
        "source_url": candidate.source_url,
        "image_url": candidate.image_url,
        "activity_ids": candidate.activity_ids,
        "compatibility": candidate.compatibility,
        "budget_delta": candidate.budget_delta,
        "expires_at": candidate.expires_at,
        "my_reaction": reaction.value if reaction else None,
        "position": candidate.position,
    }


def public_dvizh(session: Session, dvizh: DvizhSession, user_id: str) -> dict[str, object]:
    expire(session, dvizh)
    own = dvizh.initiator_id == user_id
    group = session.get(Group, dvizh.group_id)
    signal = session.get(Intent, dvizh.signal_id)
    all_candidates = candidates(session, dvizh.id)
    visible = (
        all_candidates
        if own and dvizh.status in {"CHOOSING_CANDIDATES", "NO_SOURCE", "PROVIDER_UNAVAILABLE"}
        else [c for c in all_candidates if c.seed]
    )
    matched = active(session, dvizh)
    confirmed: list[dict[str, str]] = []
    if dvizh.status == "GATHERED" and matched:
        for confirmation in session.scalars(
            select(DvizhConfirmation).where(
                DvizhConfirmation.candidate_id == matched.id,
                DvizhConfirmation.status == "CONFIRMED",
            )
        ):
            user = session.get(User, confirmation.user_id)
            if user:
                confirmed.append({"id": user.id, "display_name": user.display_name})
    my_confirmation = (
        session.scalar(
            select(DvizhConfirmation).where(
                DvizhConfirmation.candidate_id == matched.id, DvizhConfirmation.user_id == user_id
            )
        )
        if matched
        else None
    )
    return {
        "id": dvizh.id,
        "group_id": dvizh.group_id,
        "group_name": group.name if group else "Компания",
        "signal_batch_id": signal.signal_batch_id if own and signal else None,
        "status": dvizh.status,
        "is_initiator": own,
        "activity_ids": dvizh.activity_ids,
        "min_people": dvizh.min_people,
        "max_people": dvizh.max_people,
        "available_from": signal.available_from if signal else None,
        "available_to": signal.available_to if signal else None,
        "expires_at": dvizh.expires_at,
        "active_candidate_id": dvizh.active_candidate_id,
        "candidates": [
            public_candidate(session, c, user_id)
            for c in visible
            if aware(c.expires_at) > now() or dvizh.status == "GATHERED"
        ],
        "chosen_count": sum(1 for c in all_candidates if c.seed)
        if dvizh.status != "CHOOSING_CANDIDATES"
        else sum(
            1
            for c in all_candidates
            if session.scalar(
                select(DvizhReaction.id).where(
                    DvizhReaction.candidate_id == c.id,
                    DvizhReaction.user_id == user_id,
                    DvizhReaction.value == "WOULD_GO",
                )
            )
        ),
        "reaction_count": reaction_count(session, matched.id) if matched else 0,
        "confirmed_count": confirmation_count(session, matched.id) if matched else 0,
        "my_confirmation": my_confirmation.status if my_confirmation else None,
        "participants": confirmed,
    }
