"""Product API for Signal -> finite candidate choice -> group Dvizh."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import AutoSignalIn, SignalBatchIn
from app.db.models import (
    DvizhCandidate,
    DvizhConfirmation,
    DvizhReaction,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    Location,
    OutboxNotification,
    User,
)
from app.modules.leisure.provider import KudaGoProvider, ProviderQuery, fetch_items
from app.modules.leisure.taxonomy import taxonomy_out, valid_selection
from app.modules.matching.dvizh import (
    active,
    add_candidates,
    aware,
    candidates,
    confirmation_count,
    conflict,
    enqueue,
    expire,
    fail,
    get_dvizh,
    member,
    now,
    public_dvizh,
    recompute,
)

router = APIRouter(tags=["dvizh"])


class ReactionIn(BaseModel):
    value: str = Field(pattern="^(WOULD_GO|PASS)$")
    confirm_near_exception: bool = False


class ConfirmationIn(BaseModel):
    confirm_near_exception: bool = False
    candidate_id: str = Field(min_length=1)


class PlaceSearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=80)


def _query(payload: SignalBatchIn, city: str) -> ProviderQuery:
    return ProviderQuery(
        city_slug=city,
        starts_at=payload.available_from,
        ends_at=payload.available_to,
        categories=tuple(payload.activity_categories),
        product=True,
    )


def _source_available(candidate: DvizhCandidate) -> bool | None:
    if candidate.provider != "KUDAGO":
        return None
    return KudaGoProvider().item_available(
        candidate.item_type,
        candidate.provider_item_id,
        aware(candidate.starts_at),
        aware(candidate.ends_at),
    )


def _validate_groups(
    payload: SignalBatchIn, session: DbSession, user: CurrentUser
) -> tuple[list[Group], str]:
    if not valid_selection(payload.activity_categories):
        raise fail(422, "Выбери доступное занятие")
    groups: list[Group] = []
    for group_id in payload.group_ids:
        group = session.get(Group, group_id)
        if group is None or not member(session, group_id, user.id):
            raise fail(404, "Компания не найдена")
        groups.append(group)
    cities = {group.default_city_slug for group in groups}
    if len(cities) != 1:
        raise fail(422, "Выбери компании из одного города")
    city = next(iter(cities))
    if payload.origin_location_id:
        location = session.get(Location, payload.origin_location_id)
        if location is None or location.user_id != user.id or location.city_slug != city:
            raise fail(422, "Выбери своё место в городе компании")
    if payload.available_to <= now() or payload.available_from >= payload.available_to:
        raise fail(422, "Укажи время в будущем")
    return groups, city


def _existing_batch(
    session: DbSession, user: CurrentUser, batch_id: str
) -> dict[str, object] | None:
    existing = list(
        session.scalars(
            select(Intent).where(
                Intent.signal_batch_id == batch_id,
                Intent.user_id == user.id,
                Intent.flow_version == 2,
            )
        )
    )
    if not existing:
        return None
    existing_dvizhi = [
        session.scalar(select(DvizhSession).where(DvizhSession.signal_id == intent.id))
        for intent in existing
    ]
    return {
        "signal_batch_id": batch_id,
        "dvizhi": [
            public_dvizh(session, dvizh, user.id) for dvizh in existing_dvizhi if dvizh is not None
        ],
    }


def _create(
    payload: SignalBatchIn,
    session: DbSession,
    user: CurrentUser,
    request_id: str | None = None,
    replace_id: str | None = None,
) -> dict[str, object]:
    groups, city = _validate_groups(payload, session, user)
    batch_id = request_id or str(uuid4())
    if (existing := _existing_batch(session, user, batch_id)) is not None:
        return existing
    # Provider I/O is outside the transaction and the per-user lock.
    session.commit()
    result = fetch_items(_query(payload, city))
    session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    groups, city = _validate_groups(payload, session, user)
    if (existing := _existing_batch(session, user, batch_id)) is not None:
        return existing
    if replace_id:
        old = list(
            session.scalars(
                select(Intent).where(
                    Intent.signal_batch_id == replace_id,
                    Intent.user_id == user.id,
                    Intent.flow_version == 2,
                    Intent.status == "ACTIVE",
                )
            )
        )
        if not old:
            raise fail(404, "Сигнал не найден")
        for intent in old:
            dvizh = session.scalar(
                select(DvizhSession).where(DvizhSession.signal_id == intent.id).with_for_update()
            )
            if dvizh and dvizh.status not in {
                "CHOOSING_CANDIDATES",
                "NO_SOURCE",
                "PROVIDER_UNAVAILABLE",
            }:
                raise fail(409, "Движ уже запущен")
            intent.status = "CANCELLED"
            if dvizh:
                dvizh.status = "CANCELLED"
    output: list[dict[str, object]] = []
    for group in groups:
        signal = Intent(
            user_id=user.id,
            group_id=group.id,
            type="ONE_TIME",
            status="ACTIVE",
            flow_version=2,
            signal_batch_id=batch_id,
            city_slug=city,
            activity_category=payload.activity_categories[0],
            activity_categories=payload.activity_categories,
            provider_state="SEARCHING",
            available_from=payload.available_from,
            available_to=payload.available_to,
            budget_max=payload.budget_max,
            origin_location_id=payload.origin_location_id,
            radius_km=payload.radius_km,
            min_people=payload.min_people,
            max_people=payload.max_people or 12,
            expires_at=payload.available_to + timedelta(minutes=30),
        )
        session.add(signal)
        session.flush()
        dvizh = DvizhSession(
            signal_id=signal.id,
            group_id=group.id,
            initiator_id=user.id,
            status="PROVIDER_UNAVAILABLE" if result.unavailable else "CHOOSING_CANDIDATES",
            activity_ids=payload.activity_categories,
            min_people=signal.min_people,
            max_people=signal.max_people or 12,
            expires_at=signal.expires_at,
        )
        session.add(dvizh)
        session.flush()
        count = 0 if result.unavailable else add_candidates(session, dvizh, signal, result.items)
        if not result.unavailable and count == 0:
            dvizh.status = "NO_SOURCE"
        signal.provider_state = (
            "PROVIDER_UNAVAILABLE"
            if result.unavailable
            else "CANDIDATES_READY"
            if count
            else "NO_SOURCE"
        )
        session.flush()
        output.append(public_dvizh(session, dvizh, user.id))
    session.commit()
    return {"signal_batch_id": batch_id, "dvizhi": output}


def _recurring_occurrence(rule: Intent, current: datetime) -> SignalBatchIn | None:
    recurrence = rule.recurrence_json or {}
    timezone = recurrence.get("timezone")
    weekdays = recurrence.get("weekdays")
    start_text = recurrence.get("local_start")
    end_text = recurrence.get("local_end")
    if (
        not isinstance(timezone, str)
        or not isinstance(weekdays, list)
        or not isinstance(start_text, str)
        or not isinstance(end_text, str)
    ):
        return None
    zone = ZoneInfo(timezone)
    local = current.astimezone(zone)
    start_time = time.fromisoformat(start_text)
    end_time = time.fromisoformat(end_text)
    for offset in range(2):
        day = local.date() + timedelta(days=offset)
        if day.weekday() not in weekdays:
            continue
        begin = datetime.combine(day, start_time, zone).astimezone(current.tzinfo)
        finish = datetime.combine(day, end_time, zone).astimezone(current.tzinfo)
        if (
            begin <= current + timedelta(minutes=30)
            or begin > current + timedelta(hours=36)
            or finish <= begin
        ):
            continue
        return SignalBatchIn(
            group_ids=[rule.group_id],
            activity_categories=rule.activity_categories or [],
            available_from=begin,
            available_to=finish,
            budget_max=rule.budget_max,
            origin_location_id=rule.origin_location_id,
            radius_km=rule.radius_km,
            min_people=rule.min_people,
            max_people=rule.max_people,
        )
    return None


def materialize_recurring(
    session: DbSession, rule: Intent, user: User, current: datetime | None = None
) -> bool:
    if rule.status != "ACTIVE" or rule.flow_version != 2:
        return False
    occurrence = _recurring_occurrence(rule, current or now())
    if occurrence is None:
        return False
    batch_id = str(uuid5(NAMESPACE_URL, f"dvizh:{rule.id}:{occurrence.available_from.isoformat()}"))
    if session.scalar(select(Intent.id).where(Intent.signal_batch_id == batch_id)):
        return False
    result = _create(occurrence, session, user, batch_id)
    children = list(
        session.scalars(
            select(Intent).where(Intent.signal_batch_id == batch_id, Intent.flow_version == 2)
        )
    )
    for child in children:
        child.recurrence_json = {"parent_rule_id": rule.id}
    created_dvizhi = result.get("dvizhi")
    for item in created_dvizhi if isinstance(created_dvizhi, list) else []:
        if isinstance(item, dict) and item.get("status") == "CHOOSING_CANDIDATES":
            dvizh = session.get(DvizhSession, item["id"])
            if dvizh:
                enqueue(session, "DVIZH_INITIATOR_REVIEW", user.id, dvizh)
    session.commit()
    return True


@router.post("/recurring-signals", status_code=201)
def create_recurring(
    payload: AutoSignalIn, session: DbSession, user: CurrentUser
) -> dict[str, str]:
    if not valid_selection(payload.activity_categories or []):
        raise fail(422, "Выбери доступное занятие")
    group = session.get(Group, payload.group_id)
    if group is None or not member(session, group.id, user.id):
        raise fail(404, "Компания не найдена")
    if payload.origin_location_id:
        location = session.get(Location, payload.origin_location_id)
        if (
            location is None
            or location.user_id != user.id
            or location.city_slug != group.default_city_slug
        ):
            raise fail(422, "Выбери своё место в городе компании")
    rule = Intent(
        user_id=user.id,
        group_id=group.id,
        type="RECURRING",
        flow_version=2,
        status="ACTIVE",
        name=payload.name,
        city_slug=group.default_city_slug,
        activity_category=(payload.activity_categories or [])[0],
        activity_categories=payload.activity_categories,
        provider_state="SCHEDULED",
        recurrence_json={
            "weekdays": payload.weekdays,
            "local_start": payload.local_start,
            "local_end": payload.local_end,
            "timezone": payload.timezone,
        },
        budget_max=payload.budget_max,
        origin_location_id=payload.origin_location_id,
        radius_km=payload.radius_km,
        min_people=payload.min_people,
        max_people=payload.max_people,
    )
    session.add(rule)
    session.commit()
    materialize_recurring(session, rule, user)
    return {"id": rule.id, "status": rule.status}


@router.put("/recurring-signals/{rule_id}")
def edit_recurring(
    rule_id: str, payload: AutoSignalIn, session: DbSession, user: CurrentUser
) -> dict[str, str]:
    rule = session.get(Intent, rule_id)
    if (
        rule is None
        or rule.user_id != user.id
        or rule.type != "RECURRING"
        or rule.flow_version != 2
        or rule.status not in {"ACTIVE", "PAUSED"}
    ):
        raise fail(404, "Регулярный сигнал не найден")
    delete_recurring(rule_id, session, user)
    return create_recurring(payload, session, user)


def _recurring_rule(rule_id: str, session: DbSession, user: CurrentUser) -> Intent:
    rule = session.get(Intent, rule_id)
    if (
        rule is None
        or rule.user_id != user.id
        or rule.type != "RECURRING"
        or rule.flow_version != 2
    ):
        raise fail(404, "Регулярный сигнал не найден")
    return rule


def _cancel_pending_occurrences(rule: Intent, session: DbSession, user: CurrentUser) -> None:
    for child in session.scalars(
        select(Intent).where(
            Intent.user_id == user.id,
            Intent.flow_version == 2,
            Intent.type == "ONE_TIME",
            Intent.status == "ACTIVE",
        )
    ):
        if (child.recurrence_json or {}).get("parent_rule_id") != rule.id:
            continue
        dvizh = session.scalar(select(DvizhSession).where(DvizhSession.signal_id == child.id))
        if dvizh and dvizh.status in {"CHOOSING_CANDIDATES", "NO_SOURCE", "PROVIDER_UNAVAILABLE"}:
            child.status = "CANCELLED"
            dvizh.status = "CANCELLED"


@router.post("/recurring-signals/{rule_id}/pause")
def pause_recurring(rule_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    rule = _recurring_rule(rule_id, session, user)
    if rule.status not in {"ACTIVE", "PAUSED"}:
        raise fail(404, "Регулярный сигнал не найден")
    rule.status = "PAUSED"
    _cancel_pending_occurrences(rule, session, user)
    session.commit()
    return {"id": rule.id, "status": rule.status}


@router.post("/recurring-signals/{rule_id}/resume")
def resume_recurring(rule_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    rule = _recurring_rule(rule_id, session, user)
    if rule.status != "PAUSED":
        raise fail(404, "Регулярный сигнал не найден")
    rule.status = "ACTIVE"
    session.commit()
    materialize_recurring(session, rule, user)
    return {"id": rule.id, "status": rule.status}


@router.delete("/recurring-signals/{rule_id}")
def delete_recurring(rule_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    rule = _recurring_rule(rule_id, session, user)
    if rule.status == "DELETED":
        raise fail(404, "Регулярный сигнал не найден")
    rule.status = "DELETED"
    _cancel_pending_occurrences(rule, session, user)
    session.commit()
    return {"id": rule.id, "status": rule.status}


@router.get("/leisure/taxonomy")
def taxonomy() -> dict[str, object]:
    return taxonomy_out()


@router.post("/signals", status_code=201)
def create_signal(
    payload: SignalBatchIn,
    session: DbSession,
    user: CurrentUser,
    x_request_id: str | None = Header(default=None),
) -> dict[str, object]:
    if x_request_id and (len(x_request_id) > 64 or not x_request_id.isascii()):
        raise fail(422, "Некорректный идентификатор запроса")
    return _create(payload, session, user, x_request_id)


@router.put("/signals/{batch_id}")
def edit_signal(
    batch_id: str,
    payload: SignalBatchIn,
    session: DbSession,
    user: CurrentUser,
    x_request_id: str | None = Header(default=None),
) -> dict[str, object]:
    if x_request_id and (len(x_request_id) > 64 or not x_request_id.isascii()):
        raise fail(422, "Некорректный идентификатор запроса")
    return _create(payload, session, user, request_id=x_request_id, replace_id=batch_id)


@router.delete("/signals/{batch_id}")
def cancel_signal(batch_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    intents = list(
        session.scalars(
            select(Intent).where(
                Intent.signal_batch_id == batch_id,
                Intent.user_id == user.id,
                Intent.flow_version == 2,
                Intent.status == "ACTIVE",
            )
        )
    )
    if not intents:
        raise fail(404, "Сигнал не найден")
    for intent in intents:
        dvizh = session.scalar(
            select(DvizhSession).where(DvizhSession.signal_id == intent.id).with_for_update()
        )
        if dvizh and dvizh.status not in {
            "CHOOSING_CANDIDATES",
            "NO_SOURCE",
            "PROVIDER_UNAVAILABLE",
        }:
            raise fail(409, "Запущенный движ нельзя остановить через сигнал")
        intent.status = "CANCELLED"
        if dvizh:
            dvizh.status = "CANCELLED"
    session.commit()
    return {"status": "cancelled"}


@router.get("/dvizhi")
def list_dvizhi(session: DbSession, user: CurrentUser) -> list[dict[str, object]]:
    group_ids = select(GroupMember.group_id).where(GroupMember.user_id == user.id)
    launched_candidates = (
        select(DvizhCandidate.id)
        .where(DvizhCandidate.session_id == DvizhSession.id, DvizhCandidate.seed.is_(True))
        .exists()
    )
    result: list[dict[str, object]] = []
    for dvizh in session.scalars(
        select(DvizhSession)
        .where(
            DvizhSession.group_id.in_(group_ids),
            (DvizhSession.initiator_id == user.id) | launched_candidates,
        )
        .order_by(DvizhSession.created_at.desc())
        .limit(100)
    ):
        result.append(public_dvizh(session, dvizh, user.id))
    return result


@router.get("/dvizhi/{dvizh_id}")
def get_dvizh_detail(dvizh_id: str, session: DbSession, user: CurrentUser) -> dict[str, object]:
    return public_dvizh(session, get_dvizh(session, dvizh_id, user.id), user.id)


@router.post("/dvizhi/{dvizh_id}/more")
def more(dvizh_id: str, session: DbSession, user: CurrentUser) -> dict[str, object]:
    dvizh = get_dvizh(session, dvizh_id, user.id)
    if dvizh.initiator_id != user.id or dvizh.status not in {
        "CHOOSING_CANDIDATES",
        "NO_SOURCE",
        "PROVIDER_UNAVAILABLE",
    }:
        raise fail(409, "Выбор уже завершён")
    signal = session.get(Intent, dvizh.signal_id)
    assert signal and signal.available_from and signal.available_to
    query = ProviderQuery(
        city_slug=signal.city_slug,
        starts_at=signal.available_from,
        ends_at=signal.available_to,
        categories=tuple(dvizh.activity_ids),
        product=True,
    )
    session.commit()
    result = fetch_items(query, force_refresh=True)
    dvizh = get_dvizh(session, dvizh_id, user.id, lock=True)
    if dvizh.status not in {"CHOOSING_CANDIDATES", "NO_SOURCE", "PROVIDER_UNAVAILABLE"}:
        raise fail(409, "Выбор уже завершён")
    if not result.unavailable:
        add_candidates(session, dvizh, signal, result.items)
        session.flush()
    dvizh.status = (
        "PROVIDER_UNAVAILABLE"
        if result.unavailable
        else "CHOOSING_CANDIDATES"
        if candidates(session, dvizh.id)
        else "NO_SOURCE"
    )
    session.commit()
    return public_dvizh(session, dvizh, user.id)


@router.post("/dvizhi/{dvizh_id}/places/search")
def search_place(
    dvizh_id: str, payload: PlaceSearchIn, session: DbSession, user: CurrentUser
) -> dict[str, object]:
    if len(payload.query.strip()) < 2:
        raise fail(422, "Укажи название места")
    dvizh = get_dvizh(session, dvizh_id, user.id)
    if dvizh.initiator_id != user.id or dvizh.status not in {
        "CHOOSING_CANDIDATES",
        "NO_SOURCE",
        "PROVIDER_UNAVAILABLE",
    }:
        raise fail(409, "Поиск доступен до запуска движа")
    signal = session.get(Intent, dvizh.signal_id)
    assert signal and signal.available_from and signal.available_to
    query = ProviderQuery(
        city_slug=signal.city_slug,
        starts_at=signal.available_from,
        ends_at=signal.available_to,
        categories=tuple(dvizh.activity_ids),
        product=True,
    )
    session.commit()
    try:
        items = KudaGoProvider().search_place_items(query, payload.query.strip())
    except (httpx.HTTPError, ValueError) as error:
        raise fail(503, "Источник временно недоступен") from error
    dvizh = get_dvizh(session, dvizh_id, user.id, lock=True)
    if dvizh.status not in {"CHOOSING_CANDIDATES", "NO_SOURCE", "PROVIDER_UNAVAILABLE"}:
        raise fail(409, "Поиск доступен до запуска движа")
    add_candidates(session, dvizh, signal, items)
    session.flush()
    dvizh.status = "CHOOSING_CANDIDATES" if candidates(session, dvizh.id) else "NO_SOURCE"
    session.commit()
    return public_dvizh(session, dvizh, user.id)


@router.put("/dvizhi/{dvizh_id}/candidates/{candidate_id}/reaction")
def react(
    dvizh_id: str, candidate_id: str, payload: ReactionIn, session: DbSession, user: CurrentUser
) -> dict[str, object]:
    dvizh = get_dvizh(session, dvizh_id, user.id, lock=True)
    expire(session, dvizh)
    owner = dvizh.initiator_id == user.id
    if dvizh.status not in (
        {"CHOOSING_CANDIDATES"} if owner else {"COLLECTING_REACTIONS", "AWAITING_CONFIRMATION"}
    ):
        raise fail(409, "Выбор уже закрыт")
    candidate = session.get(DvizhCandidate, candidate_id)
    if (
        candidate is None
        or candidate.session_id != dvizh.id
        or (not owner and not candidate.seed)
        or aware(candidate.expires_at) <= now()
    ):
        raise fail(404, "Вариант устарел")
    if candidate.compatibility == "UNVERIFIED":
        raise fail(409, "Условия варианта не подтверждены")
    if (
        payload.value == "WOULD_GO"
        and candidate.compatibility == "NEAR"
        and not payload.confirm_near_exception
    ):
        raise fail(409, "Подтверди отличие условий")
    if payload.value == "WOULD_GO" and conflict(session, user.id, candidate):
        raise fail(409, "У тебя уже есть движ на это время")
    current = session.scalar(
        select(DvizhReaction).where(
            DvizhReaction.candidate_id == candidate.id, DvizhReaction.user_id == user.id
        )
    )
    if current is None:
        current = DvizhReaction(candidate_id=candidate.id, user_id=user.id, value=payload.value)
        session.add(current)
    else:
        if (
            dvizh.status == "AWAITING_CONFIRMATION"
            and candidate.id == dvizh.active_candidate_id
            and current.value != payload.value
        ):
            raise fail(409, "Для этого места уже идёт подтверждение")
        current.value = payload.value
    current.near_consented_at = (
        now() if payload.value == "WOULD_GO" and candidate.compatibility == "NEAR" else None
    )
    session.flush()
    if not owner:
        recompute(session, dvizh)
    session.commit()
    return public_dvizh(session, dvizh, user.id)


@router.post("/dvizhi/{dvizh_id}/launch")
def launch(dvizh_id: str, session: DbSession, user: CurrentUser) -> dict[str, object]:
    preview = get_dvizh(session, dvizh_id, user.id)
    selected = []
    if preview.status == "CHOOSING_CANDIDATES":
        for candidate in candidates(session, preview.id):
            if aware(candidate.expires_at) <= now():
                continue
            if session.scalar(
                select(DvizhReaction.id).where(
                    DvizhReaction.candidate_id == candidate.id,
                    DvizhReaction.user_id == user.id,
                    DvizhReaction.value == "WOULD_GO",
                )
            ):
                selected.append(candidate)
    # Keep provider I/O outside the row lock and transaction.
    session.commit()
    availability = {candidate.id: _source_available(candidate) for candidate in selected}
    dvizh = get_dvizh(session, dvizh_id, user.id, lock=True)
    expire(session, dvizh)
    if dvizh.initiator_id != user.id:
        raise fail(403, "Запустить движ может автор сигнала")
    if dvizh.status in {"COLLECTING_REACTIONS", "AWAITING_CONFIRMATION", "GATHERED"}:
        return public_dvizh(session, dvizh, user.id)
    if dvizh.status != "CHOOSING_CANDIDATES":
        raise fail(409, "Нет подходящих вариантов")
    seed = []
    for candidate in candidates(session, dvizh.id):
        if aware(candidate.expires_at) <= now():
            continue
        reaction = session.scalar(
            select(DvizhReaction).where(
                DvizhReaction.candidate_id == candidate.id,
                DvizhReaction.user_id == user.id,
                DvizhReaction.value == "WOULD_GO",
            )
        )
        if reaction:
            if candidate.id not in availability:
                raise fail(409, "Выбор изменился. Попробуй запустить движ ещё раз")
            if availability[candidate.id] is False:
                candidate.expires_at = now()
                continue
            candidate.seed = True
            seed.append(candidate)
    if not seed:
        if any(available is False for available in availability.values()):
            expire(session, dvizh)
            session.commit()
        raise fail(409, "Сначала отметь место, куда пошёл бы")
    dvizh.status = "COLLECTING_REACTIONS"
    session.flush()
    for user_id in session.scalars(
        select(GroupMember.user_id).where(
            GroupMember.group_id == dvizh.group_id, GroupMember.user_id != user.id
        )
    ):
        if any(not conflict(session, user_id, candidate) for candidate in seed):
            enqueue(session, "DVIZH_REVIEW_REQUIRED", user_id, dvizh)
    recompute(session, dvizh)
    session.commit()
    return public_dvizh(session, dvizh, user.id)


@router.post("/dvizhi/{dvizh_id}/confirm")
def confirm(
    dvizh_id: str, payload: ConfirmationIn, session: DbSession, user: CurrentUser
) -> dict[str, object]:
    preview = get_dvizh(session, dvizh_id, user.id)
    preview_candidate = active(session, preview)
    candidate_id = preview_candidate.id if preview_candidate else None
    session.commit()
    availability = (
        _source_available(preview_candidate)
        if preview_candidate and preview.status in {"AWAITING_CONFIRMATION", "GATHERED"}
        else None
    )
    dvizh = get_dvizh(session, dvizh_id, user.id, lock=True)
    expire(session, dvizh)
    candidate = active(session, dvizh)
    if (
        candidate is None
        or dvizh.status not in {"AWAITING_CONFIRMATION", "GATHERED"}
        or aware(candidate.expires_at) <= now()
    ):
        raise fail(409, "Подтверждение уже закрыто")
    if candidate.id != candidate_id:
        raise fail(409, "Выбранное место изменилось. Открой актуальный движ")
    if payload.candidate_id != candidate.id:
        raise fail(409, "Это место уже не выбрано. Открой актуальный движ")
    if availability is False:
        candidate.expires_at = now()
        for notification in session.scalars(
            select(OutboxNotification).where(
                OutboxNotification.status == "PENDING",
                OutboxNotification.dedupe_key.like(f"DVIZH_MATCH_FOUND:{dvizh.id}:{candidate.id}:%")
                | OutboxNotification.dedupe_key.like(f"DVIZH_GATHERED:{dvizh.id}:{candidate.id}:%"),
            )
        ):
            notification.status = "CANCELLED"
        if dvizh.status == "GATHERED":
            dvizh.status = "CANCELLED"
            signal = session.get(Intent, dvizh.signal_id)
            if signal and signal.flow_version == 2 and signal.status == "FULFILLED":
                signal.status = "EXPIRED"
            for confirmed in session.scalars(
                select(DvizhConfirmation).where(
                    DvizhConfirmation.candidate_id == candidate.id,
                    DvizhConfirmation.status == "CONFIRMED",
                )
            ):
                enqueue(session, "DVIZH_SOURCE_CANCELLED", confirmed.user_id, dvizh, candidate)
        else:
            recompute(session, dvizh)
        session.commit()
        raise fail(409, "Место больше недоступно. Проверь актуальный движ")
    reaction = session.scalar(
        select(DvizhReaction).where(
            DvizhReaction.candidate_id == candidate.id,
            DvizhReaction.user_id == user.id,
            DvizhReaction.value == "WOULD_GO",
        )
    )
    if reaction is None:
        raise fail(403, "Сначала выбери этот вариант")
    if candidate.compatibility == "NEAR" and not (
        reaction.near_consented_at or payload.confirm_near_exception
    ):
        raise fail(409, "Подтверди отличие условий")
    if conflict(session, user.id, candidate):
        raise fail(409, "У тебя уже есть движ на это время")
    existing = session.scalar(
        select(DvizhConfirmation).where(
            DvizhConfirmation.candidate_id == candidate.id, DvizhConfirmation.user_id == user.id
        )
    )
    if existing and existing.status == "CONFIRMED":
        return public_dvizh(session, dvizh, user.id)
    count = confirmation_count(session, candidate.id)
    if existing and existing.status == "WAITLISTED" and count >= dvizh.max_people:
        return public_dvizh(session, dvizh, user.id)
    status = "WAITLISTED" if count >= dvizh.max_people else "CONFIRMED"
    if existing:
        existing.status = status
    else:
        session.add(DvizhConfirmation(candidate_id=candidate.id, user_id=user.id, status=status))
    session.flush()
    if dvizh.status != "GATHERED" and confirmation_count(session, candidate.id) >= dvizh.min_people:
        dvizh.status = "GATHERED"
        signal = session.get(Intent, dvizh.signal_id)
        if signal and signal.status == "ACTIVE":
            signal.status = "FULFILLED"
        for confirmed in session.scalars(
            select(DvizhConfirmation).where(
                DvizhConfirmation.candidate_id == candidate.id,
                DvizhConfirmation.status == "CONFIRMED",
            )
        ):
            enqueue(session, "DVIZH_GATHERED", confirmed.user_id, dvizh, candidate)
    elif dvizh.status == "GATHERED" and status == "CONFIRMED":
        enqueue(session, "DVIZH_GATHERED", user.id, dvizh, candidate)
    session.commit()
    return public_dvizh(session, dvizh, user.id)


@router.post("/dvizhi/{dvizh_id}/decline")
def decline(dvizh_id: str, session: DbSession, user: CurrentUser) -> dict[str, object]:
    dvizh = get_dvizh(session, dvizh_id, user.id, lock=True)
    candidate = active(session, dvizh)
    if dvizh.status != "AWAITING_CONFIRMATION" or candidate is None:
        raise fail(409, "Подтверждение уже закрыто")
    if not session.scalar(
        select(DvizhReaction.id).where(
            DvizhReaction.candidate_id == candidate.id,
            DvizhReaction.user_id == user.id,
            DvizhReaction.value == "WOULD_GO",
        )
    ):
        raise fail(403, "Нет выбора для этого места")
    existing = session.scalar(
        select(DvizhConfirmation).where(
            DvizhConfirmation.candidate_id == candidate.id, DvizhConfirmation.user_id == user.id
        )
    )
    if existing and existing.status == "CONFIRMED":
        raise fail(409, "Участие уже подтверждено")
    if existing:
        existing.status = "DECLINED"
    else:
        session.add(
            DvizhConfirmation(candidate_id=candidate.id, user_id=user.id, status="DECLINED")
        )
    session.flush()
    recompute(session, dvizh)
    session.commit()
    return public_dvizh(session, dvizh, user.id)
