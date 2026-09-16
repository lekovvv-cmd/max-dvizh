from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import (
    AutoSignalIn,
    CityOut,
    GroupCreate,
    GroupOut,
    IntentIn,
    IntentOut,
    JoinOut,
    LocationIn,
    LocationOut,
    OfferAction,
    OfferOut,
    PlanOut,
    SessionOut,
)
from app.core.config import settings
from app.db.models import (
    CandidatePlan,
    CandidatePlanMember,
    CandidatePlanSourceSnapshot,
    Group,
    GroupMember,
    Intent,
    Location,
    Offer,
    User,
)
from app.modules.leisure.provider import (
    KudaGoProvider,
    NormalizedLeisureItem,
    ProviderQuery,
    fetch_items,
)
from app.modules.matching.domain import overlaps
from app.modules.matching.service import (
    candidate_count,
    cleanup_expired,
    recompute_candidate_plan,
    regenerate_group,
)

router = APIRouter(tags=["product"])


def now() -> datetime:
    return datetime.now(UTC)


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
    )


def intent_out(intent: Intent) -> IntentOut:
    return IntentOut(
        id=intent.id,
        type=intent.type,
        status=intent.status,
        name=intent.name,
        city_slug=intent.city_slug,
        activity_category=intent.activity_category,
        budget_max=intent.budget_max,
        radius_km=intent.radius_km,
        min_people=intent.min_people,
        max_people=intent.max_people,
        expires_at=intent.expires_at,
    )


@router.get("/session", response_model=SessionOut)
def get_session(user: CurrentUser) -> SessionOut:
    return SessionOut(
        id=user.id,
        display_name=user.display_name,
        max_mode="MAX" if settings.app_env != "development" else "development",
    )


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


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, session: DbSession, user: CurrentUser) -> GroupOut:
    group = Group(name=payload.name, default_city_slug=payload.city_slug, created_by=user.id)
    session.add(group)
    session.flush()
    session.add(GroupMember(group_id=group.id, user_id=user.id, role="OWNER"))
    session.commit()
    return group_out(session, group, expose_token=True)


@router.post("/groups/join/{token}", response_model=JoinOut)
def join_group(token: str, session: DbSession, user: CurrentUser) -> JoinOut:
    group = session.scalar(select(Group).where(Group.invite_token == token))
    if group is None:
        raise error(status.HTTP_404_NOT_FOUND, "Приглашение недействительно или истекло")
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
        select(Location).where(Location.user_id == user.id).order_by(Location.created_at.desc())
    )
    return [
        LocationOut(id=item.id, label=item.label, city_slug=item.city_slug, kind=item.kind)
        for item in locations
    ]


@router.post("/locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationIn, session: DbSession, user: CurrentUser) -> LocationOut:
    location = Location(user_id=user.id, **payload.model_dump())
    session.add(location)
    session.commit()
    session.refresh(location)
    return LocationOut(
        id=location.id, label=location.label, city_slug=location.city_slug, kind=location.kind
    )


def _create_intent(
    payload: IntentIn,
    session: DbSession,
    user: CurrentUser,
    type_: str,
    name: str | None = None,
    recurrence: dict[str, object] | None = None,
) -> IntentOut:
    member(session, payload.group_id, user.id)
    location = (
        session.get(Location, payload.origin_location_id)
        if payload.origin_location_id is not None
        else None
    )
    if payload.origin_location_id is not None and (location is None or location.user_id != user.id):
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Точка отправления не найдена")
    if payload.min_people > payload.max_people:
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Минимум участников больше максимума")
    if type_ == "ONE_TIME" and (
        payload.available_from is None
        or payload.available_to is None
        or payload.available_from >= payload.available_to
    ):
        raise error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Укажите корректное окно времени")
    intent = Intent(
        user_id=user.id,
        type=type_,
        status="ACTIVE",
        name=name,
        recurrence_json=recurrence,
        **payload.model_dump(),
    )
    session.add(intent)
    session.commit()
    session.refresh(intent)
    provider_result = fetch_items(_provider_query(payload, type_))
    if not provider_result.unavailable:
        regenerate_group(session, payload.group_id, payload.city_slug, provider_result.items)
    return intent_out(intent)


def _provider_query(payload: IntentIn, intent_type: str) -> ProviderQuery:
    if intent_type == "ONE_TIME":
        assert payload.available_from is not None and payload.available_to is not None
        starts_at, ends_at = payload.available_from, payload.available_to
    else:
        starts_at = now()
        ends_at = starts_at + timedelta(days=7)
    categories = () if payload.activity_category in {"any", "other"} else (payload.activity_category,)
    return ProviderQuery(
        city_slug=payload.city_slug,
        starts_at=starts_at,
        ends_at=ends_at,
        categories=categories,
    )


@router.post("/intents", response_model=IntentOut, status_code=status.HTTP_201_CREATED)
def create_signal(payload: IntentIn, session: DbSession, user: CurrentUser) -> IntentOut:
    return _create_intent(payload, session, user, "ONE_TIME")


@router.get("/intents", response_model=list[IntentOut])
def list_intents(group_id: str, session: DbSession, user: CurrentUser) -> list[IntentOut]:
    member(session, group_id, user.id)
    intents = session.scalars(
        select(Intent)
        .where(Intent.group_id == group_id, Intent.user_id == user.id)
        .order_by(Intent.created_at.desc())
    )
    return [intent_out(item) for item in intents]


@router.post("/autosignals", response_model=IntentOut, status_code=status.HTTP_201_CREATED)
def create_auto_signal(payload: AutoSignalIn, session: DbSession, user: CurrentUser) -> IntentOut:
    recurrence: dict[str, object] = {
        "weekdays": payload.weekdays,
        "local_start": payload.local_start,
        "local_end": payload.local_end,
        "timezone": payload.timezone,
    }
    return _create_intent(payload, session, user, "RECURRING", payload.name, recurrence)


@router.post("/autosignals/{intent_id}/{action}", response_model=IntentOut)
def change_auto_signal(
    intent_id: str, action: str, session: DbSession, user: CurrentUser
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
    potential = (
        session.scalar(
            select(func.count())
            .select_from(CandidatePlanMember)
            .where(
                CandidatePlanMember.candidate_plan_id == plan.id,
                CandidatePlanMember.compatibility.in_(("EXACT", "NEAR")),
            )
        )
        or 0
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
        potential_count=potential,
        required_min_people=plan.required_min_people,
        required_max_people=plan.required_max_people,
        expires_at=offer.expires_at,
        budget_delta=membership.budget_delta if offer.is_near else None,
    )


@router.get("/offers", response_model=list[OfferOut])
def list_offers(session: DbSession, user: CurrentUser) -> list[OfferOut]:
    cleanup_expired(session)
    session.commit()
    offers = list(
        session.scalars(
            select(Offer)
            .where(Offer.user_id == user.id, Offer.status == "PENDING", Offer.expires_at > now())
            .order_by(Offer.created_at.desc())
        )
    )
    # This is the user's global pool across every group. Ordering is convenience
    # only: it must never become a product limit.
    return [offer_out(session, offer) for offer in offers]


@router.post("/offers/{offer_id}/accept", response_model=OfferOut)
def accept_offer(
    offer_id: str, payload: OfferAction, session: DbSession, user: CurrentUser
) -> OfferOut:
    # PostgreSQL lock order is User -> CandidatePlan -> Offer. User locking
    # serializes competing actions by one participant; plan locking serializes
    # capacity/confirmation changes by different participants.
    preliminary = session.get(Offer, offer_id)
    if preliminary is None or preliminary.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Предложение не найдено")
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    plan = session.scalar(
        select(CandidatePlan).where(CandidatePlan.id == preliminary.candidate_plan_id).with_for_update()
    )
    offer = session.scalar(select(Offer).where(Offer.id == offer_id).with_for_update())
    if offer is None or offer.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Предложение не найдено")
    if offer.status == "ACCEPTED":
        return offer_out(session, offer)
    if offer.status != "PENDING" or offer.expires_at <= now():
        raise error(status.HTTP_409_CONFLICT, "Предложение уже недоступно")
    if offer.is_near and not payload.confirm_near_exception:
        raise error(status.HTTP_409_CONFLICT, "Подтвердите небольшое превышение бюджета")
    assert plan is not None
    if plan.status != "COLLECTING" or plan.expires_at <= now():
        raise error(status.HTTP_409_CONFLICT, "План больше не собирается")
    accepted = candidate_count(session, plan.id)
    if accepted >= plan.required_max_people:
        raise error(status.HTTP_409_CONFLICT, "В плане уже набрано достаточно участников")
    for other in session.scalars(
        select(Offer).where(Offer.user_id == user.id, Offer.status == "ACCEPTED")
    ):
        other_plan = session.get(CandidatePlan, other.candidate_plan_id)
        if other_plan and overlaps(
            plan.starts_at, plan.ends_at, other_plan.starts_at, other_plan.ends_at
        ):
            raise error(status.HTTP_409_CONFLICT, "В это время уже есть подтверждённое участие")
    offer.status = "ACCEPTED"
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
    for affected in session.scalars(
        select(CandidatePlan)
        .where(CandidatePlan.id.in_(affected_plan_ids))
        .order_by(CandidatePlan.id)
        .with_for_update()
    ):
        recompute_candidate_plan(session, affected)
    session.commit()
    return offer_out(session, offer)


@router.post("/offers/{offer_id}/reject", response_model=OfferOut)
def reject_offer(offer_id: str, session: DbSession, user: CurrentUser) -> OfferOut:
    preliminary = session.get(Offer, offer_id)
    if preliminary is None or preliminary.user_id != user.id:
        raise error(status.HTTP_404_NOT_FOUND, "Предложение не найдено")
    session.scalar(select(User).where(User.id == user.id).with_for_update())
    plan = session.scalar(
        select(CandidatePlan).where(CandidatePlan.id == preliminary.candidate_plan_id).with_for_update()
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


def plan_out(session: DbSession, plan: CandidatePlan) -> PlanOut:
    snapshot = session.scalar(
        select(CandidatePlanSourceSnapshot).where(
            CandidatePlanSourceSnapshot.candidate_plan_id == plan.id
        )
    )
    assert snapshot is not None
    participants = candidate_count(session, plan.id)
    price = f" · {snapshot.price_text}" if snapshot.price_text else ""
    share = f"⚡ ДВИЖ СОБРАЛСЯ: {snapshot.title}, {plan.starts_at.strftime('%d.%m %H:%M')}{price}"
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
        required_min_people=plan.required_min_people,
        required_max_people=plan.required_max_people,
        share_text=share,
    )


@router.get("/plans", response_model=list[PlanOut])
def list_plans(session: DbSession, user: CurrentUser) -> list[PlanOut]:
    ids = select(Offer.candidate_plan_id).where(
        Offer.user_id == user.id, Offer.status == "ACCEPTED"
    )
    plans = session.scalars(
        select(CandidatePlan)
        .where(CandidatePlan.id.in_(ids), CandidatePlan.status == "CONFIRMED")
        .order_by(CandidatePlan.starts_at)
    )
    return [plan_out(session, plan) for plan in plans]


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: str, session: DbSession, user: CurrentUser) -> PlanOut:
    plan = session.get(CandidatePlan, plan_id)
    accepted = (
        session.scalar(
            select(Offer).where(
                Offer.candidate_plan_id == plan_id,
                Offer.user_id == user.id,
                Offer.status == "ACCEPTED",
            )
        )
        if plan
        else None
    )
    if plan is None or accepted is None:
        raise error(status.HTTP_404_NOT_FOUND, "План не найден")
    return plan_out(session, plan)


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
        ProviderQuery(city_slug=city_slug, starts_at=starts_at, ends_at=starts_at + timedelta(days=7))
    )
    if result.unavailable:
        raise error(status.HTTP_503_SERVICE_UNAVAILABLE, "Данные KudaGo временно недоступны")
    return {"count": len(result.items), "cached": result.cached, "fetched_at": result.fetched_at}


@router.post("/development/seed-demo/{group_id}", status_code=status.HTTP_201_CREATED)
def seed_demo(group_id: str, session: DbSession, user: CurrentUser) -> dict[str, str]:
    if settings.app_env != "development":
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
