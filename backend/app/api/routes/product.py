from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import (
    AutoSignalIn,
    CityOut,
    GroupCityUpdateIn,
    GroupCityUpdateOut,
    GroupCreate,
    GroupMemberOut,
    GroupOut,
    IntentIn,
    IntentOut,
    JoinOut,
    LocationIn,
    LocationOut,
    LocationRenameIn,
    OfferAction,
    OfferOut,
    PlanOut,
    PlanParticipantOut,
    SessionOut,
    SignalBatchIn,
    SignalBatchOut,
)
from app.core.config import settings
from app.core.timezones import display_timezone
from app.db.models import (
    CandidatePlan,
    CandidatePlanMember,
    CandidatePlanSourceSnapshot,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    Location,
    Offer,
    OutboxNotification,
    User,
)
from app.modules.auth.service import optional_max_chat_id
from app.modules.leisure.provider import (
    KudaGoProvider,
    NormalizedLeisureItem,
    ProviderQuery,
    ProviderResult,
    fetch_items,
)
from app.modules.matching.domain import overlaps
from app.modules.matching.scheduler import evaluate_auto_signal
from app.modules.matching.service import (
    _has_other_overlap,
    cleanup_expired,
    confirmed_count,
    effective_capacity,
    recompute_candidate_plan,
    regenerate_group,
    response_count,
)

router = APIRouter(tags=["product"])
TIME_OF_DAY = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    """SQLite drops timezone information; persisted timestamps are UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def metadata_text(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None


def error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def member(session: DbSession, group_id: str, user_id: str) -> Group:
    group = session.get(Group, group_id)
    is_member = session.scalar(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    if group is None or is_member is None:
        raise error(status.HTTP_404_NOT_FOUND, "Группа не найдена")
    return group


def supported_cities() -> dict[str, dict[str, str]]:
    try:
        return {city["slug"]: city for city in KudaGoProvider().cities()}
    except Exception as exc:
        raise error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Список городов временно недоступен"
        ) from exc


def group_out(session: DbSession, group: Group, expose_token: bool = False) -> GroupOut:
    count = (
        session.scalar(
            select(func.count()).select_from(GroupMember).where(GroupMember.group_id == group.id)
        )
        or 0
    )
    return GroupOut(
        id=group.id,
        name=group.name,
        city_slug=group.default_city_slug,
        member_count=count,
        invite_token=group.invite_token if expose_token else None,
        invite_url=(
            f"https://max.ru/{settings.max_bot_username}?startapp={group.invite_token}"
            if expose_token and settings.max_bot_username
            else None
        ),
        max_chat_bound=group.max_chat_id is not None,
    )


def recurrence_display_fields(
    recurrence: dict[str, object] | None,
) -> tuple[list[int] | None, str | None, str | None]:
    """Return only well-formed recurring fields that are safe to display to the owner."""
    data = recurrence or {}
    raw_weekdays = data.get("weekdays")
    weekdays: list[int] | None = None
    if isinstance(raw_weekdays, list):
        parsed_weekdays: list[int] = []
        for day in raw_weekdays:
            if type(day) is not int or day < 0 or day > 6:
                break
            parsed_weekdays.append(day)
        else:
            weekdays = parsed_weekdays or None

    raw_start = data.get("local_start")
    local_start = (
        raw_start if isinstance(raw_start, str) and TIME_OF_DAY.fullmatch(raw_start) else None
    )
    raw_end = data.get("local_end")
    local_end = raw_end if isinstance(raw_end, str) and TIME_OF_DAY.fullmatch(raw_end) else None
    return weekdays, local_start, local_end


def intent_out(intent: Intent, group_name: str | None = None) -> IntentOut:
    weekdays, local_start, local_end = recurrence_display_fields(intent.recurrence_json)
    return IntentOut(
        id=intent.id,
        type=intent.type,
        status=intent.status,
        provider_state=intent.provider_state,
        name=intent.name,
        city_slug=intent.city_slug,
        activity_category=intent.activity_category,
        activity_categories=intent.activity_categories or [intent.activity_category],
        signal_batch_id=intent.signal_batch_id,
        group_id=intent.group_id,
        group_name=group_name,
        budget_max=intent.budget_max,
        radius_km=intent.radius_km,
        origin_location_id=intent.origin_location_id,
        min_people=intent.min_people,
        max_people=intent.max_people,
        available_from=intent.available_from,
        available_to=intent.available_to,
        expires_at=intent.expires_at,
        weekdays=weekdays if intent.type == "RECURRING" else None,
        local_start=local_start if intent.type == "RECURRING" else None,
        local_end=local_end if intent.type == "RECURRING" else None,
    )


@router.get("/session", response_model=SessionOut)
def get_session(
    user: CurrentUser, x_max_init_data: str | None = Header(default=None)
) -> SessionOut:
    return SessionOut(
        id=user.id,
        display_name=user.display_name,
        max_mode="development" if settings.local_demo_mode else "MAX",
        max_chat_id=optional_max_chat_id(x_max_init_data),
        onboarding_seen=user.onboarding_seen_at is not None,
    )


@router.post("/session/onboarding-seen", response_model=SessionOut)
def mark_onboarding_seen(
    session: DbSession, user: CurrentUser, x_max_init_data: str | None = Header(default=None)
) -> SessionOut:
    if user.onboarding_seen_at is None:
        user.onboarding_seen_at = now()
        session.commit()
    return get_session(user, x_max_init_data)


@router.get("/groups", response_model=list[GroupOut])
def list_groups(session: DbSession, user: CurrentUser) -> list[GroupOut]:
    groups = list(
        session.scalars(
            select(Group)
            .join(GroupMember)
            .where(GroupMember.user_id == user.id)
            .order_by(Group.created_at.desc())
        )
    )
    return [group_out(session, group, expose_token=True) for group in groups]


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberOut])
def list_group_members(
    group_id: str, session: DbSession, user: CurrentUser
) -> list[GroupMemberOut]:
    member(session, group_id, user.id)
    rows = session.execute(
        select(User.id, User.display_name)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at, GroupMember.id)
    ).all()
    return [
        GroupMemberOut(id=user_id, display_name=display_name, is_me=user_id == user.id)
        for user_id, display_name in rows
    ]


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    session: DbSession,
    user: CurrentUser,
    x_max_init_data: str | None = Header(default=None),
) -> GroupOut:
    supported = supported_cities()
    if payload.city_slug not in supported:
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Город пока не поддерживается")
    chat_id = optional_max_chat_id(x_max_init_data) if payload.bind_current_chat else None
    if payload.bind_current_chat and chat_id is None:
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Открой ДВИЖ из группового чата MAX")
    if chat_id is not None:
        if session.scalar(select(Group.id).where(Group.max_chat_id == chat_id)) is not None:
            raise error(status.HTTP_409_CONFLICT, "Для этого чата уже создана компания")
        try:
            response = httpx.get(
                f"{settings.max_bot_api_base}/chats/{chat_id}",
                headers={"Authorization": settings.max_bot_token},
                timeout=5,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Не удалось проверить чат MAX. Бот должен иметь доступ к чату",
            ) from exc
        chat = response.json()
        if chat.get("type") != "chat":
            raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Нужен групповой чат MAX")
        if chat.get("status") != "active":
            raise error(status.HTTP_409_CONFLICT, "Бот не участвует в этом чате")
    group = Group(
        name=payload.name,
        default_city_slug=payload.city_slug,
        timezone_name=supported[payload.city_slug].get("timezone"),
        max_chat_id=chat_id,
        created_by=user.id,
    )
    session.add(group)
    session.flush()
    session.add(GroupMember(group_id=group.id, user_id=user.id, role="OWNER"))
    session.commit()
    return group_out(session, group, expose_token=True)


@router.put("/groups/{group_id}/city", response_model=GroupCityUpdateOut)
def update_group_city(
    group_id: str,
    payload: GroupCityUpdateIn,
    session: DbSession,
    user: CurrentUser,
) -> GroupCityUpdateOut:
    group = member(session, group_id, user.id)
    membership = session.scalar(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user.id)
    )
    assert membership is not None
    if group.created_by != user.id and membership.role != "OWNER":
        raise error(status.HTTP_403_FORBIDDEN, "Только владелец компании может изменить город")
    session.commit()

    supported = supported_cities()
    city = supported.get(payload.city_slug)
    if city is None:
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Город пока не поддерживается")
    locked_group = session.scalar(select(Group).where(Group.id == group_id).with_for_update())
    if locked_group is None:
        raise error(status.HTTP_404_NOT_FOUND, "Группа не найдена")
    group = locked_group
    if group.default_city_slug == payload.city_slug:
        group.timezone_name = city.get("timezone") or "UTC"
        session.commit()
        return GroupCityUpdateOut(
            group=group_out(session, group, expose_token=True),
            cancelled_signals=0,
            paused_autosignals=0,
            cancelled_plans=0,
            invalidated_offers=0,
        )

    active_intents = list(
        session.scalars(
            select(Intent).where(Intent.group_id == group.id, Intent.status == "ACTIVE")
        )
    )
    cancelled_signals = 0
    paused_autosignals = 0
    for intent in active_intents:
        if intent.type == "ONE_TIME":
            intent.status = "CANCELLED"
            cancelled_signals += 1
            if intent.flow_version == 2:
                dvizh = session.scalar(
                    select(DvizhSession).where(DvizhSession.signal_id == intent.id)
                )
                if dvizh and dvizh.status not in {"GATHERED", "CANCELLED", "EXPIRED"}:
                    dvizh.status = "CANCELLED"
                    for notification in session.scalars(
                        select(OutboxNotification).where(
                            OutboxNotification.status == "PENDING",
                            OutboxNotification.kind.in_(
                                (
                                    "DVIZH_INITIATOR_REVIEW",
                                    "DVIZH_REVIEW_REQUIRED",
                                    "DVIZH_MATCH_FOUND",
                                )
                            ),
                        )
                    ):
                        if notification.payload.get("dvizh_id") == dvizh.id:
                            notification.status = "CANCELLED"
        elif intent.type == "RECURRING":
            intent.status = "PAUSED"
            paused_autosignals += 1

    mutable_plans = list(
        session.scalars(
            select(CandidatePlan).where(
                CandidatePlan.group_id == group.id,
                CandidatePlan.status.in_(("COLLECTING", "CONFIRMED_OPEN")),
            )
        )
    )
    cancelled_plans = 0
    invalidated_offers = 0
    invalidated_offer_ids: set[str] = set()
    for plan in mutable_plans:
        invalidatable: tuple[str, ...] = ("PENDING", "WAITING_CONDITION", "WAITLISTED")
        if plan.status == "COLLECTING":
            plan.status = "CANCELLED"
            cancelled_plans += 1
            invalidatable = (*invalidatable, "ACCEPTED")
        for offer in session.scalars(
            select(Offer).where(
                Offer.candidate_plan_id == plan.id,
                Offer.status.in_(invalidatable),
            )
        ):
            offer.status = "INVALIDATED"
            invalidated_offers += 1
            invalidated_offer_ids.add(offer.id)

    if invalidated_offer_ids:
        for notification in session.scalars(
            select(OutboxNotification).where(
                OutboxNotification.kind == "OFFER",
                OutboxNotification.status == "PENDING",
            )
        ):
            if notification.payload.get("offer_id") in invalidated_offer_ids:
                notification.status = "CANCELLED"

    group.default_city_slug = payload.city_slug
    group.timezone_name = city.get("timezone") or "UTC"
    session.commit()
    return GroupCityUpdateOut(
        group=group_out(session, group, expose_token=True),
        cancelled_signals=cancelled_signals,
        paused_autosignals=paused_autosignals,
        cancelled_plans=cancelled_plans,
        invalidated_offers=invalidated_offers,
    )


@router.post("/groups/join/{token}", response_model=JoinOut)
def join_group(token: str, session: DbSession, user: CurrentUser) -> JoinOut:
    group = session.scalar(select(Group).where(Group.invite_token == token))
    if group is None:
        raise error(status.HTTP_404_NOT_FOUND, "Приглашение недействительно")
    if group.invite_expires_at is not None and aware(group.invite_expires_at) <= now():
        raise error(status.HTTP_410_GONE, "Приглашение истекло")
    existing = session.scalar(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id)
    )
    if existing is None:
        session.add(GroupMember(group_id=group.id, user_id=user.id, role="MEMBER"))
        session.commit()
    return JoinOut(
        group=group_out(session, group, expose_token=True), already_member=existing is not None
    )


@router.get("/locations", response_model=list[LocationOut])
def list_locations(session: DbSession, user: CurrentUser) -> list[LocationOut]:
    locations = session.scalars(
        select(Location)
        .where(Location.user_id == user.id, Location.is_ephemeral.is_(False))
        .order_by(Location.is_default.desc(), Location.created_at.desc())
    )
    return [location_out(item) for item in locations]


def location_out(location: Location) -> LocationOut:
    return LocationOut(
        id=location.id,
        label=location.label,
        city_slug=location.city_slug,
        kind=location.kind,
        address_text=location.address_text,
        is_default=location.is_default,
    )


def own_location(session: DbSession, user_id: str, location_id: str) -> Location:
    location = session.get(Location, location_id)
    if location is None or location.user_id != user_id or location.is_ephemeral:
        raise error(status.HTTP_404_NOT_FOUND, "Место не найдено")
    return location


@router.post("/locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationIn, session: DbSession, user: CurrentUser) -> LocationOut:
    if payload.is_ephemeral:
        raise error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Сохрани место, чтобы использовать расстояние"
        )
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    city_is_joined = session.scalar(
        select(Group.id)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user.id, Group.default_city_slug == payload.city_slug)
        .limit(1)
    )
    if city_is_joined is None:
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Выбери город своей компании")
    has_default = session.scalar(
        select(Location.id)
        .where(
            Location.user_id == user.id,
            Location.city_slug == payload.city_slug,
            Location.is_ephemeral.is_(False),
            Location.is_default.is_(True),
        )
        .limit(1)
    )
    location = Location(user_id=user.id, **payload.model_dump())
    location.is_default = has_default is None
    session.add(location)
    session.commit()
    session.refresh(location)
    return location_out(location)


@router.patch("/locations/{location_id}", response_model=LocationOut)
def rename_location(
    location_id: str, payload: LocationRenameIn, session: DbSession, user: CurrentUser
) -> LocationOut:
    location = own_location(session, user.id, location_id)
    location.label = payload.label.strip()
    if not location.label:
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Укажи название места")
    session.commit()
    return location_out(location)


@router.post("/locations/{location_id}/default", response_model=LocationOut)
def default_location(location_id: str, session: DbSession, user: CurrentUser) -> LocationOut:
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    location = own_location(session, user.id, location_id)
    for place in session.scalars(
        select(Location).where(
            Location.user_id == user.id,
            Location.city_slug == location.city_slug,
            Location.is_default.is_(True),
        )
    ):
        place.is_default = False
    location.is_default = True
    session.commit()
    return location_out(location)


@router.delete("/locations/{location_id}")
def delete_location(location_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    location = own_location(session, user.id, location_id)
    referencing = list(
        session.scalars(select(Intent).where(Intent.origin_location_id == location.id))
    )
    if any(intent.status == "ACTIVE" for intent in referencing):
        raise error(
            status.HTTP_409_CONFLICT,
            "Место используется в сигнале. Сначала убери ограничение расстояния в сигнале",
        )
    for intent in referencing:
        intent.origin_location_id = None
        intent.radius_km = None
    was_default = location.is_default
    city = location.city_slug
    session.delete(location)
    session.flush()
    if was_default:
        replacement = session.scalar(
            select(Location)
            .where(
                Location.user_id == user.id,
                Location.city_slug == city,
                Location.is_ephemeral.is_(False),
            )
            .order_by(Location.created_at.desc())
            .limit(1)
        )
        if replacement is not None:
            replacement.is_default = True
    session.commit()
    return {"status": "deleted"}


def _create_intent(
    payload: IntentIn,
    session: DbSession,
    user: CurrentUser,
    type_: str,
    name: str | None = None,
    recurrence: dict[str, object] | None = None,
) -> IntentOut:
    group = member(session, payload.group_id, user.id)
    location = (
        session.get(Location, payload.origin_location_id)
        if payload.origin_location_id is not None
        else None
    )
    if payload.origin_location_id is not None and (
        location is None
        or location.user_id != user.id
        or location.city_slug != group.default_city_slug
    ):
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Точка отправления не найдена")
    if payload.city_slug is not None and payload.city_slug != group.default_city_slug:
        raise error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Город сигнала должен совпадать с городом компании",
        )
    if type_ == "ONE_TIME" and (
        payload.available_from is None
        or payload.available_to is None
        or payload.available_from >= payload.available_to
    ):
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Укажите корректное окно времени")
    values = payload.model_dump(
        exclude={"name", "weekdays", "local_start", "local_end", "timezone"}
    )
    values["city_slug"] = group.default_city_slug
    values["activity_categories"] = payload.activity_categories or [payload.activity_category]
    values["expires_at"] = (
        payload.available_to + timedelta(minutes=30)
        if type_ == "ONE_TIME" and payload.available_to is not None
        else None
    )
    intent = Intent(
        user_id=user.id,
        type=type_,
        status="ACTIVE",
        name=name,
        recurrence_json=recurrence,
        **values,
    )
    session.add(intent)
    session.commit()
    session.refresh(intent)
    if type_ == "ONE_TIME":
        provider_result = fetch_items(_provider_query(payload, type_, group.default_city_slug))
        if not provider_result.unavailable:
            regenerate_group(
                session, payload.group_id, group.default_city_slug, provider_result.items
            )
    return intent_out(intent)


def _provider_query(payload: IntentIn, intent_type: str, city_slug: str) -> ProviderQuery:
    if intent_type == "ONE_TIME":
        assert payload.available_from is not None and payload.available_to is not None
        starts_at, ends_at = payload.available_from, payload.available_to
    else:
        starts_at = now()
        ends_at = starts_at + timedelta(days=7)
    selected = payload.activity_categories or [payload.activity_category]
    categories = () if "any" in selected or "other" in selected else tuple(selected)
    return ProviderQuery(
        city_slug=city_slug,
        starts_at=starts_at,
        ends_at=ends_at,
        categories=categories,
    )


@router.post("/intents", response_model=IntentOut, status_code=status.HTTP_201_CREATED)
def create_signal(payload: IntentIn, session: DbSession, user: CurrentUser) -> IntentOut:
    if not settings.local_demo_mode:
        raise error(status.HTTP_410_GONE, "Используй новый экран сигналов")
    return _create_intent(payload, session, user, "ONE_TIME")


def _batch_groups(
    payload: SignalBatchIn, session: DbSession, user: CurrentUser
) -> tuple[list[Group], str]:
    groups = [member(session, group_id, user.id) for group_id in payload.group_ids]
    cities = {group.default_city_slug for group in groups}
    if len(cities) != 1:
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Выберите компании из одного города")
    city = cities.pop()
    if payload.origin_location_id:
        location = session.get(Location, payload.origin_location_id)
        if location is None or location.user_id != user.id or location.city_slug != city:
            raise error(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Выберите своё место в городе компании"
            )
    return groups, city


def _refresh_batch(
    session: DbSession, intents: list[Intent], city: str, result: ProviderResult
) -> None:
    if not intents:
        return
    if result.unavailable:
        for intent in intents:
            intent.provider_state = "PROVIDER_UNAVAILABLE"
    else:
        for group_id in sorted({intent.group_id for intent in intents}):
            regenerate_group(session, group_id, city, result.items, commit=False)
        for intent in intents:
            visible = session.scalar(
                select(Offer.id)
                .join(
                    CandidatePlanMember,
                    CandidatePlanMember.candidate_plan_id == Offer.candidate_plan_id,
                )
                .where(
                    CandidatePlanMember.intent_id == intent.id,
                    Offer.user_id == intent.user_id,
                    Offer.status.in_(("PENDING", "ACCEPTED", "WAITING_CONDITION", "WAITLISTED")),
                )
                .limit(1)
            )
            intent.provider_state = (
                "OFFERS_READY" if visible else "NO_FEASIBLE_PLAN" if result.items else "NO_SOURCE"
            )


def _batch_query(
    city: str, starts_at: datetime, ends_at: datetime, categories: list[str]
) -> ProviderQuery:
    return ProviderQuery(
        city_slug=city,
        starts_at=starts_at,
        ends_at=ends_at,
        categories=() if "any" in categories else tuple(categories),
    )


def _save_batch(
    payload: SignalBatchIn, session: DbSession, user: CurrentUser, batch_id: str | None = None
) -> SignalBatchOut:
    groups, city = _batch_groups(payload, session, user)
    # Complete all provider I/O before mutating Intent rows or holding locks.
    session.commit()
    result = fetch_items(
        _batch_query(
            city, payload.available_from, payload.available_to, payload.activity_categories
        )
    )
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    groups, city = _batch_groups(payload, session, user)
    editing = batch_id is not None
    batch_id = batch_id or str(uuid4())
    existing = list(
        session.scalars(
            select(Intent).where(Intent.signal_batch_id == batch_id, Intent.user_id == user.id)
        )
    )
    if editing and not any(intent.status == "ACTIVE" for intent in existing):
        raise error(status.HTTP_404_NOT_FOUND, "Сигнал не найден")
    for intent in existing:
        intent.status = "CANCELLED"
    created: list[Intent] = []
    for group in groups:
        intent = Intent(
            user_id=user.id,
            group_id=group.id,
            type="ONE_TIME",
            status="ACTIVE",
            signal_batch_id=batch_id,
            city_slug=city,
            activity_category=payload.activity_categories[0],
            activity_categories=payload.activity_categories,
            available_from=payload.available_from,
            available_to=payload.available_to,
            budget_max=payload.budget_max,
            origin_location_id=payload.origin_location_id
            if payload.radius_km is not None
            else None,
            radius_km=payload.radius_km,
            min_people=payload.min_people,
            max_people=payload.max_people,
            expires_at=payload.available_to + timedelta(minutes=30),
        )
        session.add(intent)
        created.append(intent)
    session.flush()
    _refresh_batch(session, created, city, result)
    for plan in session.scalars(
        select(CandidatePlan).where(
            CandidatePlan.group_id.in_([intent.group_id for intent in existing]),
            CandidatePlan.status.in_(("COLLECTING", "CONFIRMED_OPEN")),
        )
    ):
        recompute_candidate_plan(session, plan)
    session.commit()
    return SignalBatchOut(
        signal_batch_id=batch_id, intents=[intent_out(intent) for intent in created]
    )


@router.post("/signal-batches/{batch_id}/refresh", response_model=SignalBatchOut)
def refresh_signal_batch(batch_id: str, session: DbSession, user: CurrentUser) -> SignalBatchOut:
    if not settings.local_demo_mode:
        raise error(status.HTTP_410_GONE, "Используй новый экран сигналов")
    intents = list(
        session.scalars(
            select(Intent).where(
                Intent.signal_batch_id == batch_id,
                Intent.user_id == user.id,
                Intent.type == "ONE_TIME",
                Intent.status == "ACTIVE",
            )
        )
    )
    if not intents:
        raise error(status.HTTP_404_NOT_FOUND, "Сигнал не найден")
    first = intents[0]
    assert first.available_from is not None and first.available_to is not None
    query = _batch_query(
        first.city_slug,
        first.available_from,
        first.available_to,
        first.activity_categories or [first.activity_category],
    )
    session.commit()
    result = fetch_items(query)
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    intents = list(
        session.scalars(
            select(Intent).where(
                Intent.signal_batch_id == batch_id,
                Intent.user_id == user.id,
                Intent.type == "ONE_TIME",
                Intent.status == "ACTIVE",
            )
        )
    )
    if (
        not intents
        or intents[0].available_from is None
        or intents[0].available_to is None
        or _batch_query(
            intents[0].city_slug,
            intents[0].available_from,
            intents[0].available_to,
            intents[0].activity_categories or [intents[0].activity_category],
        )
        != query
    ):
        raise error(status.HTTP_409_CONFLICT, "Сигнал изменился. Повтори поиск")
    _refresh_batch(session, intents, intents[0].city_slug, result)
    session.commit()
    return SignalBatchOut(
        signal_batch_id=batch_id, intents=[intent_out(intent) for intent in intents]
    )


@router.post("/signal-batches", response_model=SignalBatchOut, status_code=status.HTTP_201_CREATED)
def create_signal_batch(
    payload: SignalBatchIn, session: DbSession, user: CurrentUser
) -> SignalBatchOut:
    if not settings.local_demo_mode:
        raise error(status.HTTP_410_GONE, "Используй новый экран сигналов")
    return _save_batch(payload, session, user)


@router.put("/signal-batches/{batch_id}", response_model=SignalBatchOut)
def edit_signal_batch(
    batch_id: str, payload: SignalBatchIn, session: DbSession, user: CurrentUser
) -> SignalBatchOut:
    if not settings.local_demo_mode:
        raise error(status.HTTP_410_GONE, "Используй новый экран сигналов")
    current = session.scalar(
        select(Intent).where(
            Intent.signal_batch_id == batch_id,
            Intent.user_id == user.id,
            Intent.type == "ONE_TIME",
            Intent.status == "ACTIVE",
        )
    )
    if current is None:
        raise error(status.HTTP_404_NOT_FOUND, "Сигнал не найден")
    return _save_batch(payload, session, user, batch_id)


@router.delete("/signal-batches/{batch_id}")
def cancel_signal_batch(batch_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    intents = list(
        session.scalars(
            select(Intent).where(
                Intent.signal_batch_id == batch_id,
                Intent.user_id == user.id,
                Intent.type == "ONE_TIME",
                Intent.status == "ACTIVE",
            )
        )
    )
    if not intents:
        raise error(status.HTTP_404_NOT_FOUND, "Сигнал не найден")
    for intent in intents:
        intent.status = "CANCELLED"
    affected = set(intent.group_id for intent in intents)
    session.flush()
    for plan in session.scalars(
        select(CandidatePlan).where(
            CandidatePlan.group_id.in_(affected),
            CandidatePlan.status.in_(("COLLECTING", "CONFIRMED_OPEN")),
        )
    ):
        recompute_candidate_plan(session, plan)
    session.commit()
    return {"status": "cancelled"}


@router.get("/intents", response_model=list[IntentOut])
def list_intents(
    session: DbSession, user: CurrentUser, group_id: str | None = None
) -> list[IntentOut]:
    if group_id is not None:
        member(session, group_id, user.id)
    query = select(Intent).where(Intent.user_id == user.id)
    if group_id is not None:
        query = query.where(Intent.group_id == group_id)
    intents = session.scalars(query.order_by(Intent.created_at.desc()))
    return [
        intent_out(item, group.name if (group := session.get(Group, item.group_id)) else "Компания")
        for item in intents
    ]


@router.post("/autosignals", response_model=IntentOut, status_code=status.HTTP_201_CREATED)
def create_auto_signal(
    payload: AutoSignalIn, background_tasks: BackgroundTasks, session: DbSession, user: CurrentUser
) -> IntentOut:
    if not settings.local_demo_mode:
        raise error(status.HTTP_410_GONE, "Используй новый экран сигналов")
    recurrence: dict[str, object] = {
        "weekdays": payload.weekdays,
        "local_start": payload.local_start,
        "local_end": payload.local_end,
        "timezone": payload.timezone,
    }
    created = _create_intent(payload, session, user, "RECURRING", payload.name, recurrence)
    background_tasks.add_task(evaluate_auto_signal, created.id)
    return created


@router.put("/autosignals/{intent_id}", response_model=IntentOut)
def edit_auto_signal(
    intent_id: str,
    payload: AutoSignalIn,
    background_tasks: BackgroundTasks,
    session: DbSession,
    user: CurrentUser,
) -> IntentOut:
    current = session.get(Intent, intent_id)
    if (
        current is None
        or current.user_id != user.id
        or current.type != "RECURRING"
        or current.status == "CANCELLED"
    ):
        raise error(status.HTTP_404_NOT_FOUND, "Автосигнал не найден")
    old_group_id = current.group_id
    current.status = "CANCELLED"
    replacement = create_auto_signal(payload, background_tasks, session, user)
    for plan in session.scalars(
        select(CandidatePlan).where(
            CandidatePlan.group_id == old_group_id,
            CandidatePlan.status.in_(("COLLECTING", "CONFIRMED_OPEN")),
        )
    ):
        recompute_candidate_plan(session, plan)
    session.commit()
    return replacement


@router.post("/autosignals/{intent_id}/{action}", response_model=IntentOut)
def change_auto_signal(
    intent_id: str,
    action: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
    user: CurrentUser,
) -> IntentOut:
    intent = session.get(Intent, intent_id)
    if intent is None or intent.user_id != user.id or intent.type != "RECURRING":
        raise error(status.HTTP_404_NOT_FOUND, "Автосигнал не найден")
    if action == "pause":
        intent.status = "PAUSED"
    elif action == "resume":
        intent.status = "ACTIVE"
    elif action == "cancel":
        intent.status = "CANCELLED"
    else:
        raise error(status.HTTP_404_NOT_FOUND, "Неизвестное действие")
    session.commit()
    if action == "resume":
        background_tasks.add_task(evaluate_auto_signal, intent.id)
    else:
        for plan in session.scalars(
            select(CandidatePlan).where(
                CandidatePlan.group_id == intent.group_id,
                CandidatePlan.status.in_(("COLLECTING", "CONFIRMED_OPEN")),
            )
        ):
            recompute_candidate_plan(session, plan)
        session.commit()
    return intent_out(intent)


def offer_out(session: DbSession, offer: Offer) -> OfferOut:
    plan = session.get(CandidatePlan, offer.candidate_plan_id)
    assert plan is not None
    snapshot = session.scalar(
        select(CandidatePlanSourceSnapshot).where(
            CandidatePlanSourceSnapshot.candidate_plan_id == plan.id
        )
    )
    group = session.get(Group, plan.group_id)
    membership = session.scalar(
        select(CandidatePlanMember).where(
            CandidatePlanMember.candidate_plan_id == plan.id,
            CandidatePlanMember.user_id == offer.user_id,
        )
    )
    assert snapshot is not None and membership is not None and group is not None
    accepted = confirmed_count(session, plan.id)
    responders = response_count(session, plan.id)
    capacity = effective_capacity(session, plan)
    waitlisted = (
        session.scalar(
            select(func.count())
            .select_from(Offer)
            .where(Offer.candidate_plan_id == plan.id, Offer.status == "WAITLISTED")
        )
        or 0
    )
    own_intent = session.get(Intent, membership.intent_id)
    assert own_intent is not None
    required = max(plan.required_min_people, own_intent.min_people)
    return _offer_output(
        offer,
        plan,
        snapshot,
        group,
        membership,
        accepted,
        responders,
        capacity,
        waitlisted,
        required,
        own_intent,
    )


def _offer_output(
    offer: Offer,
    plan: CandidatePlan,
    snapshot: CandidatePlanSourceSnapshot,
    group: Group,
    membership: CandidatePlanMember,
    accepted: int,
    responders: int,
    capacity: int,
    waitlisted: int,
    required: int,
    own_intent: Intent,
) -> OfferOut:
    metadata = snapshot.source_metadata or {}
    personal_capacity = (
        min(capacity, own_intent.max_people) if own_intent.max_people is not None else capacity
    )
    can_waitlist = (
        own_intent.max_people == own_intent.min_people == personal_capacity
        and responders >= personal_capacity
    )
    return OfferOut(
        id=offer.id,
        status=offer.status,
        is_near=offer.is_near,
        group_id=group.id,
        group_name=group.name,
        title=snapshot.title,
        venue_name=snapshot.venue_name,
        starts_at=plan.starts_at,
        ends_at=plan.ends_at,
        price_text=snapshot.price_text,
        price_min=snapshot.parsed_price,
        is_demo=snapshot.is_demo,
        source_url=snapshot.source_url,
        source_fetched_at=snapshot.source_fetched_at,
        distance_km=membership.distance_km,
        required_min_people=required,
        required_max_people=capacity,
        expires_at=offer.expires_at,
        budget_delta=membership.budget_delta if offer.is_near else None,
        accepted_count=accepted,
        conditional_count=responders - accepted,
        effective_max=personal_capacity,
        remaining_to_confirm=max(0, required - accepted),
        remaining_capacity=max(0, personal_capacity - responders),
        waitlist_count=waitlisted,
        can_waitlist=can_waitlist,
        can_accept=responders < personal_capacity,
        price_kind=str(metadata.get("price_kind") or "UNKNOWN"),
        opening_hours_unverified=bool(metadata.get("opening_hours_unverified")),
        address_text=metadata_text(metadata, "address_text"),
    )


@router.get("/offers", response_model=list[OfferOut])
def list_offers(session: DbSession, user: CurrentUser) -> list[OfferOut]:
    cleanup_expired(session)
    session.commit()
    offers = list(
        session.scalars(
            select(Offer)
            .where(Offer.user_id == user.id, Offer.status == "PENDING", Offer.expires_at > now())
            .join(CandidatePlan, CandidatePlan.id == Offer.candidate_plan_id)
            .order_by(CandidatePlan.starts_at, Offer.created_at)
        )
    )
    # This is the user's global pool across every group. Ordering is convenience
    # only: it must never become a product limit.
    if not offers:
        return []
    plan_ids = {offer.candidate_plan_id for offer in offers}
    plans = {
        plan.id: plan
        for plan in session.scalars(select(CandidatePlan).where(CandidatePlan.id.in_(plan_ids)))
    }
    snapshots = {
        snapshot.candidate_plan_id: snapshot
        for snapshot in session.scalars(
            select(CandidatePlanSourceSnapshot).where(
                CandidatePlanSourceSnapshot.candidate_plan_id.in_(plan_ids)
            )
        )
    }
    groups = {
        group.id: group
        for group in session.scalars(
            select(Group).where(Group.id.in_({plan.group_id for plan in plans.values()}))
        )
    }
    members = {
        member.candidate_plan_id: member
        for member in session.scalars(
            select(CandidatePlanMember).where(
                CandidatePlanMember.candidate_plan_id.in_(plan_ids),
                CandidatePlanMember.user_id == user.id,
            )
        )
    }
    own_intents = {
        intent.id: intent
        for intent in session.scalars(
            select(Intent).where(Intent.id.in_({member.intent_id for member in members.values()}))
        )
    }
    group_sizes = {
        group_id: size
        for group_id, size in session.execute(
            select(GroupMember.group_id, func.count())
            .where(GroupMember.group_id.in_(groups))
            .group_by(GroupMember.group_id)
        )
    }
    responder_rows = session.execute(
        select(Offer.candidate_plan_id, Offer.status, Intent.max_people)
        .join(
            CandidatePlanMember,
            (CandidatePlanMember.candidate_plan_id == Offer.candidate_plan_id)
            & (CandidatePlanMember.user_id == Offer.user_id),
        )
        .join(Intent, Intent.id == CandidatePlanMember.intent_id)
        .where(
            Offer.candidate_plan_id.in_(plan_ids),
            Offer.status.in_(("ACCEPTED", "WAITING_CONDITION")),
        )
    )
    responders: dict[str, list[tuple[str, int | None]]] = {}
    for plan_id, offer_status, maximum in responder_rows:
        responders.setdefault(plan_id, []).append((offer_status, maximum))
    waitlists = {
        plan_id: count
        for plan_id, count in session.execute(
            select(Offer.candidate_plan_id, func.count())
            .where(Offer.candidate_plan_id.in_(plan_ids), Offer.status == "WAITLISTED")
            .group_by(Offer.candidate_plan_id)
        )
    }
    result: list[OfferOut] = []
    for offer in offers:
        plan = plans[offer.candidate_plan_id]
        group = groups[plan.group_id]
        response_ranges = responders.get(plan.id, [])
        accepted = sum(offer_status == "ACCEPTED" for offer_status, _ in response_ranges)
        caps = [
            maximum
            for offer_status, maximum in response_ranges
            if maximum is not None and (offer_status == "ACCEPTED" or accepted == 0)
        ]
        capacity = min((group_sizes.get(group.id, 0), *caps))
        own_intent = own_intents[members[plan.id].intent_id]
        required = max(plan.required_min_people, own_intent.min_people)
        result.append(
            _offer_output(
                offer,
                plan,
                snapshots[plan.id],
                group,
                members[plan.id],
                accepted,
                len(response_ranges),
                capacity,
                waitlists.get(plan.id, 0),
                required,
                own_intent,
            )
        )
    return result


@router.post("/offers/{offer_id}/accept", response_model=OfferOut)
def accept_offer(
    offer_id: str, payload: OfferAction, session: DbSession, user: CurrentUser
) -> OfferOut:
    # PostgreSQL lock order is User -> sorted CandidatePlans -> Offer. User
    # locking serializes competing actions by one participant. Locking every
    # potentially invalidated plan in one global order prevents P1→P2 / P2→P1
    # deadlocks when two requests choose overlapping Offers concurrently.
    preliminary = session.get(Offer, offer_id)
    if preliminary is None or preliminary.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Предложение не найдено")
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    target_plan = session.get(CandidatePlan, preliminary.candidate_plan_id)
    assert target_plan is not None
    candidate_plan_ids = {target_plan.id}
    for pending_plan in session.scalars(
        select(CandidatePlan)
        .join(Offer, Offer.candidate_plan_id == CandidatePlan.id)
        .where(Offer.user_id == user.id, Offer.status == "PENDING")
    ):
        if overlaps(
            target_plan.starts_at,
            target_plan.ends_at,
            pending_plan.starts_at,
            pending_plan.ends_at,
        ):
            candidate_plan_ids.add(pending_plan.id)
    locked_plans = {
        plan.id: plan
        for plan in session.scalars(
            select(CandidatePlan)
            .where(CandidatePlan.id.in_(candidate_plan_ids))
            .order_by(CandidatePlan.id)
            .with_for_update()
        )
    }
    plan = locked_plans[preliminary.candidate_plan_id]
    offer = session.scalar(select(Offer).where(Offer.id == offer_id).with_for_update())
    if offer is None or offer.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Предложение не найдено")
    if offer.status in {"ACCEPTED", "WAITING_CONDITION", "WAITLISTED"}:
        return offer_out(session, offer)
    if offer.status != "PENDING" or aware(offer.expires_at) <= now():
        raise error(status.HTTP_409_CONFLICT, "Предложение уже недоступно")
    if offer.is_near and not payload.confirm_near_exception:
        raise error(status.HTTP_409_CONFLICT, "Подтвердите небольшое превышение бюджета")
    assert plan is not None
    if (
        plan.status not in {"COLLECTING", "CONFIRMED_OPEN", "CONFIRMED"}
        or aware(plan.expires_at) <= now()
    ):
        raise error(status.HTTP_409_CONFLICT, "План больше не собирается")
    membership = session.scalar(
        select(CandidatePlanMember).where(
            CandidatePlanMember.candidate_plan_id == plan.id, CandidatePlanMember.user_id == user.id
        )
    )
    intent = session.get(Intent, membership.intent_id) if membership else None
    if intent is None or intent.status != "ACTIVE":
        raise error(status.HTTP_409_CONFLICT, "Условия сигнала больше не действуют")
    accepted = response_count(session, plan.id)
    capacity = effective_capacity(session, plan)
    personal_capacity = (
        min(capacity, intent.max_people) if intent.max_people is not None else capacity
    )
    if accepted >= personal_capacity:
        if intent.max_people != intent.min_people or intent.max_people != personal_capacity:
            raise error(status.HTTP_409_CONFLICT, "В плане уже набрано достаточно участников")
        offer.status = "WAITLISTED"
        offer.responded_at = now()
        session.commit()
        return offer_out(session, offer)
    for other in session.scalars(
        select(Offer).where(
            Offer.user_id == user.id, Offer.status.in_(("ACCEPTED", "WAITING_CONDITION"))
        )
    ):
        other_plan = session.get(CandidatePlan, other.candidate_plan_id)
        if other_plan and overlaps(
            plan.starts_at, plan.ends_at, other_plan.starts_at, other_plan.ends_at
        ):
            raise error(status.HTTP_409_CONFLICT, "В это время уже есть подтверждённое участие")
    offer.status = "WAITING_CONDITION"
    offer.responded_at = now()
    if offer.is_near:
        offer.exception_confirmed_at = now()
    session.flush()
    affected_plan_ids: set[str] = set()
    pending = session.scalars(
        select(Offer).where(
            Offer.user_id == user.id, Offer.status == "PENDING", Offer.id != offer.id
        )
    )
    for other in pending:
        other_plan = session.get(CandidatePlan, other.candidate_plan_id)
        if other_plan and overlaps(
            plan.starts_at, plan.ends_at, other_plan.starts_at, other_plan.ends_at
        ):
            other.status = "INVALIDATED"
            affected_plan_ids.add(other_plan.id)
    recompute_candidate_plan(session, plan)
    for affected_id in sorted(affected_plan_ids):
        recompute_candidate_plan(session, locked_plans[affected_id])
    session.commit()
    return offer_out(session, offer)


@router.post("/offers/{offer_id}/cancel", response_model=OfferOut)
def cancel_accepted_offer(offer_id: str, session: DbSession, user: CurrentUser) -> OfferOut:
    preliminary = session.get(Offer, offer_id)
    if preliminary is None or preliminary.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Участие не найдено")
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    plan = session.scalar(
        select(CandidatePlan)
        .where(CandidatePlan.id == preliminary.candidate_plan_id)
        .with_for_update()
    )
    offer = session.scalar(select(Offer).where(Offer.id == offer_id).with_for_update())
    assert plan is not None and offer is not None
    if aware(plan.expires_at) <= now():
        raise error(status.HTTP_409_CONFLICT, "Время изменения участия прошло")
    if offer.status == "CANCELLED_BY_USER":
        return offer_out(session, offer)
    if offer.status not in {"ACCEPTED", "WAITING_CONDITION", "WAITLISTED"}:
        raise error(status.HTTP_409_CONFLICT, "Участие уже недоступно")
    was_waitlisted = offer.status == "WAITLISTED"
    offer.status = "CANCELLED_BY_USER"
    if not was_waitlisted:
        waiting = list(
            session.scalars(
                select(Offer)
                .where(Offer.candidate_plan_id == plan.id, Offer.status == "WAITLISTED")
                .order_by(Offer.responded_at, Offer.id)
            )
        )
        for next_offer in waiting:
            if _has_other_overlap(session, user_id=next_offer.user_id, plan=plan):
                continue
            next_offer.status = "WAITING_CONDITION"
            break
    recompute_candidate_plan(session, plan)
    # Cancellation can make overlapping Offers available again.
    for other in session.scalars(
        select(Offer).where(Offer.user_id == user.id, Offer.status == "INVALIDATED")
    ):
        other_plan = session.get(CandidatePlan, other.candidate_plan_id)
        if other_plan is not None and overlaps(
            plan.starts_at, plan.ends_at, other_plan.starts_at, other_plan.ends_at
        ):
            recompute_candidate_plan(session, other_plan)
    session.commit()
    return offer_out(session, offer)


@router.post("/offers/{offer_id}/reject", response_model=OfferOut)
def reject_offer(offer_id: str, session: DbSession, user: CurrentUser) -> OfferOut:
    preliminary = session.get(Offer, offer_id)
    if preliminary is None or preliminary.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Предложение не найдено")
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    plan = session.scalar(
        select(CandidatePlan)
        .where(CandidatePlan.id == preliminary.candidate_plan_id)
        .with_for_update()
    )
    offer = session.scalar(select(Offer).where(Offer.id == offer_id).with_for_update())
    if offer is None or offer.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Предложение не найдено")
    if offer.status == "REJECTED":
        return offer_out(session, offer)
    if offer.status != "PENDING":
        raise error(status.HTTP_409_CONFLICT, "Предложение уже обработано")
    offer.status = "REJECTED"
    assert plan is not None
    recompute_candidate_plan(session, plan)
    session.commit()
    return offer_out(session, offer)


def plan_out(session: DbSession, plan: CandidatePlan, user_id: str) -> PlanOut:
    snapshot = session.scalar(
        select(CandidatePlanSourceSnapshot).where(
            CandidatePlanSourceSnapshot.candidate_plan_id == plan.id
        )
    )
    assert snapshot is not None
    metadata = snapshot.source_metadata or {}
    participants = confirmed_count(session, plan.id)
    responders = response_count(session, plan.id)
    group = session.get(Group, plan.group_id)
    assert group is not None
    capacity = effective_capacity(session, plan)
    own_offer = session.scalar(
        select(Offer).where(
            Offer.candidate_plan_id == plan.id,
            Offer.user_id == user_id,
            Offer.status.in_(("ACCEPTED", "WAITING_CONDITION", "WAITLISTED")),
        )
    )
    own_member = (
        session.scalar(
            select(CandidatePlanMember).where(
                CandidatePlanMember.candidate_plan_id == plan.id,
                CandidatePlanMember.user_id == user_id,
            )
        )
        if own_offer
        else None
    )
    own_intent = session.get(Intent, own_member.intent_id) if own_member else None
    personal_min = (
        own_intent.min_people
        if own_offer and own_offer.status == "WAITING_CONDITION" and own_intent
        else None
    )
    visible_participants: list[PlanParticipantOut] = []
    if (
        plan.status in {"CONFIRMED", "CONFIRMED_OPEN"}
        and own_offer is not None
        and own_offer.status == "ACCEPTED"
    ):
        people = session.scalars(
            select(User)
            .join(Offer, Offer.user_id == User.id)
            .where(Offer.candidate_plan_id == plan.id, Offer.status == "ACCEPTED")
            .order_by(User.display_name)
        )
        visible_participants = [
            PlanParticipantOut(id=person.id, display_name=person.display_name) for person in people
        ]
    price = f" · {snapshot.price_text}" if snapshot.price_text else ""
    timezone_name = group.timezone_name or "UTC"
    local_start = (
        plan.starts_at.replace(tzinfo=UTC) if plan.starts_at.tzinfo is None else plan.starts_at
    )
    share = (
        f"⚡ ДВИЖ СОБРАЛСЯ: {snapshot.title}, {local_start.astimezone(display_timezone(timezone_name)).strftime('%d.%m %H:%M')}{price}"
        if plan.status in {"CONFIRMED", "CONFIRMED_OPEN"}
        and own_offer is not None
        and own_offer.status == "ACCEPTED"
        else ""
    )
    return PlanOut(
        id=plan.id,
        status=plan.status,
        title=snapshot.title,
        venue_name=snapshot.venue_name,
        starts_at=plan.starts_at,
        ends_at=plan.ends_at,
        price_text=snapshot.price_text,
        source_url=snapshot.source_url,
        participant_count=participants,
        conditional_count=responders - participants,
        personal_response_count=responders if personal_min is not None else None,
        personal_required_min=personal_min,
        required_min_people=plan.required_min_people,
        required_max_people=plan.required_max_people,
        share_text=share,
        group_id=group.id,
        group_name=group.name,
        remaining_to_confirm=max(0, plan.required_min_people - participants),
        remaining_capacity=max(0, capacity - responders),
        participants=visible_participants,
        my_offer_id=own_offer.id if own_offer else None,
        my_status=own_offer.status if own_offer else None,
        price_kind=str(metadata.get("price_kind") or "UNKNOWN"),
        opening_hours_unverified=bool(metadata.get("opening_hours_unverified")),
        address_text=metadata_text(metadata, "address_text"),
    )


@router.get("/plans", response_model=list[PlanOut])
def list_plans(session: DbSession, user: CurrentUser) -> list[PlanOut]:
    ids = select(Offer.candidate_plan_id).where(
        Offer.user_id == user.id, Offer.status.in_(("ACCEPTED", "WAITING_CONDITION", "WAITLISTED"))
    )
    plans = session.scalars(
        select(CandidatePlan)
        .where(
            CandidatePlan.id.in_(ids),
            CandidatePlan.status.in_(("COLLECTING", "CONFIRMED", "CONFIRMED_OPEN")),
            CandidatePlan.starts_at > now(),
        )
        .order_by(CandidatePlan.starts_at)
    )
    return [plan_out(session, plan, user.id) for plan in plans]


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: str, session: DbSession, user: CurrentUser) -> PlanOut:
    plan = session.get(CandidatePlan, plan_id)
    accepted = (
        session.scalar(
            select(Offer).where(
                Offer.candidate_plan_id == plan_id,
                Offer.user_id == user.id,
                Offer.status.in_(("ACCEPTED", "WAITING_CONDITION", "WAITLISTED")),
            )
        )
        if plan
        else None
    )
    if plan is None or accepted is None:
        raise error(status.HTTP_404_NOT_FOUND, "План не найден")
    return plan_out(session, plan, user.id)


@router.get("/leisure/cities", response_model=list[CityOut])
def cities() -> list[CityOut]:
    try:
        return [
            CityOut(slug=item["slug"], name=item["name"], source="KudaGo")
            for item in KudaGoProvider().cities()
        ]
    except Exception:
        return []


@router.post("/leisure/sync/{city_slug}")
def sync(city_slug: str, session: DbSession, user: CurrentUser) -> dict[str, object]:
    starts_at = now()
    result = fetch_items(
        ProviderQuery(
            city_slug=city_slug, starts_at=starts_at, ends_at=starts_at + timedelta(days=7)
        )
    )
    if result.unavailable:
        raise error(status.HTTP_503_SERVICE_UNAVAILABLE, "Данные KudaGo временно недоступны")
    return {"count": len(result.items), "cached": result.cached, "fetched_at": result.fetched_at}


@router.post("/development/seed-demo/{group_id}", status_code=status.HTTP_201_CREATED)
def seed_demo(group_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    if not settings.local_demo_mode:
        raise error(status.HTTP_404_NOT_FOUND, "Не найдено")
    group = member(session, group_id, user.id)
    start = now() + timedelta(hours=2)
    demo_item = NormalizedLeisureItem(
        provider="MODEL",
        provider_id=f"demo-{group.id}",
        item_type="MODEL",
        city_slug=group.default_city_slug,
        title="Демо: вечер в ПК-клубе",
        category="other",
        venue_name="Демо-площадка",
        latitude=56.8389,
        longitude=60.6057,
        starts_at=start,
        ends_at=start + timedelta(hours=3),
        price_text="400 ₽",
        price_min=400,
        source_url=None,
        image_url=None,
        source_fetched_at=now(),
        is_demo=True,
    )
    regenerate_group(session, group.id, group.default_city_slug, [demo_item])
    return {"status": "seeded", "label": "Демонстрационные данные"}
