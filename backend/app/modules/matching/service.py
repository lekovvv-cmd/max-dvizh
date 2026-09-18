"""Application matching flows backed by stable CandidatePlan source snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    OutboxNotification,
)
from app.modules.leisure.provider import NormalizedLeisureItem
from app.modules.matching.domain import (
    GroupSizeCandidate,
    compatibility,
    contains_interval,
    feasible_cohort,
    haversine_km,
    offer_expiry,
    overlaps,
    recurring_interval_fits,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def metadata_text(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None


@dataclass(frozen=True)
class EvaluatedCandidate:
    intent: Intent
    kind: str
    distance_km: float | None
    budget_delta: int | None

    def rank(self) -> tuple[bool, bool, float, datetime, str]:
        created = self.intent.created_at or datetime.min.replace(tzinfo=UTC)
        return (self.kind == "NEAR", self.distance_km is None, self.distance_km if self.distance_km is not None else float("inf"), created, self.intent.user_id)


def _active_intents(session: Session, group_id: str, city: str) -> list[Intent]:
    current = utcnow()
    return list(session.scalars(select(Intent).where(Intent.group_id == group_id, Intent.status == "ACTIVE", Intent.city_slug == city, (Intent.expires_at.is_(None) | (Intent.expires_at > current)))))


def _fits_time(intent: Intent, item: NormalizedLeisureItem) -> bool:
    if intent.type != "RECURRING":
        return intent.available_from is not None and intent.available_to is not None and contains_interval(intent.available_from, intent.available_to, item.starts_at, item.ends_at)
    recurrence = intent.recurrence_json or {}
    weekdays, local_start = recurrence.get("weekdays"), recurrence.get("local_start")
    local_end, timezone_name = recurrence.get("local_end"), recurrence.get("timezone")
    if not (isinstance(weekdays, list) and all(isinstance(day, int) for day in weekdays) and isinstance(local_start, str) and isinstance(local_end, str) and isinstance(timezone_name, str)):
        return False
    try:
        return recurring_interval_fits(starts_at=item.starts_at, ends_at=item.ends_at, weekdays=weekdays, local_start=local_start, local_end=local_end, timezone_name=timezone_name)
    except (ValueError, KeyError):
        return False


def _snapshot_item(snapshot: CandidatePlanSourceSnapshot, city_slug: str) -> NormalizedLeisureItem:
    metadata = snapshot.source_metadata or {}
    return NormalizedLeisureItem(provider=snapshot.provider, provider_id=snapshot.provider_item_id, item_type=snapshot.provider_item_type, city_slug=city_slug, title=snapshot.title, category=snapshot.category, venue_name=snapshot.venue_name, starts_at=snapshot.starts_at, ends_at=snapshot.ends_at, latitude=snapshot.latitude, longitude=snapshot.longitude, price_text=snapshot.price_text, price_min=snapshot.parsed_price, source_url=snapshot.source_url, image_url=snapshot.image_url, source_fetched_at=snapshot.source_fetched_at, is_demo=snapshot.is_demo, categories=tuple(cast(list[str], metadata.get("categories") or [])), price_kind=str(metadata.get("price_kind") or "UNKNOWN"), address_text=metadata_text(metadata, "address_text"), opening_hours_unverified=bool(metadata.get("opening_hours_unverified")), timetable=metadata_text(metadata, "timetable"))


def place_slots(item: NormalizedLeisureItem) -> list[NormalizedLeisureItem]:
    """Build concrete 30-minute-grid slots; matching checks each full interval."""
    if item.item_type != "PLACE" or not item.source_url:
        return []
    duration = timedelta(minutes=settings.place_plan_duration_minutes)
    start = max(item.starts_at, utcnow())
    minute_overhang = start.minute % 30
    if minute_overhang or start.second or start.microsecond:
        start += timedelta(minutes=30 - minute_overhang, seconds=-start.second, microseconds=-start.microsecond)
    result: list[NormalizedLeisureItem] = []
    while start + duration <= item.ends_at:
        result.append(replace(item, starts_at=start, ends_at=start + duration))
        start += timedelta(minutes=30)
    return result


def _evaluate_item(session: Session, group_id: str, city: str, item: NormalizedLeisureItem, *, intents: list[Intent] | None = None, locations: dict[str, Location] | None = None) -> tuple[list[EvaluatedCandidate], list[EvaluatedCandidate]]:
    eligible_by_user: dict[str, EvaluatedCandidate] = {}
    unverified_by_user: dict[str, EvaluatedCandidate] = {}
    for intent in intents if intents is not None else _active_intents(session, group_id, city):
        categories = set(intent.activity_categories or [intent.activity_category])
        item_categories = set(getattr(item, "categories", ()) or (item.category,))
        if not ({"any", "other"} & categories or categories & item_categories) or not _fits_time(intent, item):
            continue
        location = (locations.get(intent.origin_location_id) if locations is not None else session.get(Location, intent.origin_location_id)) if intent.origin_location_id else None
        distance = haversine_km(location.latitude, location.longitude, item.latitude, item.longitude) if location is not None and item.latitude is not None and item.longitude is not None else None
        result = compatibility(price=item.price_min, max_budget=intent.budget_max, near_limit=settings.near_budget_max_delta_rub, distance_km=distance, radius_km=intent.radius_km)
        candidate = EvaluatedCandidate(intent, result.kind, distance, result.budget_delta)
        target = eligible_by_user if result.kind in {"EXACT", "NEAR"} else unverified_by_user if result.kind == "UNVERIFIED" else None
        if target is not None and (target.get(intent.user_id) is None or candidate.rank() < target[intent.user_id].rank()):
            target[intent.user_id] = candidate
    return list(eligible_by_user.values()), list(unverified_by_user.values())


def _enqueue(session: Session, *, kind: str, user_id: str, payload: dict[str, object], key: str) -> None:
    if session.scalar(select(OutboxNotification.id).where(OutboxNotification.dedupe_key == key)) is None:
        session.add(OutboxNotification(kind=kind, user_id=user_id, payload=payload, dedupe_key=key, status="PENDING"))


def cleanup_expired(session: Session) -> None:
    """Query-time expiry keeps active pool and action semantics consistent."""
    current = utcnow()
    for plan in session.scalars(select(CandidatePlan).where(CandidatePlan.status.in_(("COLLECTING", "CONFIRMED_OPEN")), CandidatePlan.expires_at <= current)):
        was_confirmed = plan.status == "CONFIRMED_OPEN"
        plan.status = "CONFIRMED" if was_confirmed else "EXPIRED"
        for offer in session.scalars(select(Offer).where(Offer.candidate_plan_id == plan.id, Offer.status == "PENDING")):
            offer.status = "EXPIRED"
    for offer in session.scalars(select(Offer).where(Offer.status == "PENDING", Offer.expires_at <= current)):
        offer.status = "EXPIRED"


def _offer_statuses(session: Session, plan_id: str) -> dict[str, Offer]:
    return {offer.user_id: offer for offer in session.scalars(select(Offer).where(Offer.candidate_plan_id == plan_id))}


def _has_other_overlap(session: Session, *, user_id: str, plan: CandidatePlan) -> bool:
    for offer in session.scalars(select(Offer).where(Offer.user_id == user_id, Offer.status.in_(("ACCEPTED", "WAITING_CONDITION")), Offer.candidate_plan_id != plan.id)):
        other = session.get(CandidatePlan, offer.candidate_plan_id)
        if other is not None and overlaps(plan.starts_at, plan.ends_at, other.starts_at, other.ends_at):
            return True
    return False


def _upsert_member(session: Session, plan_id: str, candidate: EvaluatedCandidate) -> None:
    member = session.scalar(select(CandidatePlanMember).where(CandidatePlanMember.candidate_plan_id == plan_id, CandidatePlanMember.user_id == candidate.intent.user_id))
    deviation = {"type": "BUDGET_OVER_MAX", "delta": candidate.budget_delta} if candidate.kind == "NEAR" else ({"type": "MISSING_PROVIDER_CONSTRAINT_DATA"} if candidate.kind == "UNVERIFIED" else None)
    values = {"intent_id": candidate.intent.id, "compatibility": candidate.kind, "distance_km": round(candidate.distance_km, 1) if candidate.distance_km is not None else None, "budget_delta": candidate.budget_delta, "deviations_json": deviation}
    if member is None:
        session.add(CandidatePlanMember(candidate_plan_id=plan_id, user_id=candidate.intent.user_id, **values))
    else:
        for field, value in values.items():
            setattr(member, field, value)


def candidate_count(session: Session, plan_id: str) -> int:
    return session.scalar(select(func.count()).select_from(Offer).where(Offer.candidate_plan_id == plan_id, Offer.status == "ACCEPTED")) or 0


def response_count(session: Session, plan_id: str) -> int:
    return session.scalar(select(func.count()).select_from(Offer).where(Offer.candidate_plan_id == plan_id, Offer.status.in_(("ACCEPTED", "WAITING_CONDITION")))) or 0


def group_capacity(session: Session, group_id: str) -> int:
    return session.scalar(select(func.count()).select_from(GroupMember).where(GroupMember.group_id == group_id)) or 0


def effective_capacity(session: Session, plan: CandidatePlan) -> int:
    """Accepted people's explicit caps bound further admission; NULL uses company size."""
    capacity = group_capacity(session, plan.group_id)
    members = session.scalars(select(Intent.max_people).join(CandidatePlanMember, CandidatePlanMember.intent_id == Intent.id).join(Offer, (Offer.candidate_plan_id == CandidatePlanMember.candidate_plan_id) & (Offer.user_id == CandidatePlanMember.user_id)).where(CandidatePlanMember.candidate_plan_id == plan.id, Offer.status.in_(("ACCEPTED", "WAITING_CONDITION")), Intent.max_people.is_not(None)))
    return min((capacity, *members)) if capacity else 0


def recompute_candidate_plan(session: Session, plan: CandidatePlan, *, intents: list[Intent] | None = None, locations: dict[str, Location] | None = None) -> bool:
    """Refresh a plan from its source snapshot; repeated calls are idempotent."""
    cleanup_expired(session)
    if plan.status not in {"COLLECTING", "CONFIRMED_OPEN", "CONFIRMED"} or aware(plan.expires_at) <= utcnow():
        return False
    snapshot = session.scalar(select(CandidatePlanSourceSnapshot).where(CandidatePlanSourceSnapshot.candidate_plan_id == plan.id))
    if snapshot is None or plan.starts_at >= plan.ends_at:
        plan.status = "CANCELLED"
        return False
    eligible, unverified = _evaluate_item(session, plan.group_id, plan.city_slug, _snapshot_item(snapshot, plan.city_slug), intents=intents, locations=locations)
    statuses = _offer_statuses(session, plan.id)
    for candidate in [*eligible, *unverified]:
        _upsert_member(session, plan.id, candidate)
    eligible_by_user = {candidate.intent.user_id: candidate for candidate in eligible}
    for user_id, offer in statuses.items():
        if offer.status in {"ACCEPTED", "WAITING_CONDITION"} and user_id not in eligible_by_user:
            offer.status = "CANCELLED_BY_USER"
        if offer.status in {"PENDING", "INVALIDATED"}:
            if user_id not in eligible_by_user or _has_other_overlap(session, user_id=user_id, plan=plan):
                offer.status = "INVALIDATED"
            elif offer.status == "INVALIDATED" and aware(offer.expires_at) > utcnow():
                offer.status = "PENDING"
    expiry = offer_expiry(utcnow(), aware(plan.starts_at))
    if expiry is not None:
        for candidate in eligible:
            user_id = candidate.intent.user_id
            if user_id in statuses or _has_other_overlap(session, user_id=user_id, plan=plan):
                continue
            offer = Offer(candidate_plan_id=plan.id, user_id=user_id, status="PENDING", is_near=candidate.kind == "NEAR", expires_at=expiry)
            session.add(offer)
            session.flush()
            group = session.get(Group, plan.group_id)
            _enqueue(session, kind="OFFER", user_id=user_id, payload={"offer_id": offer.id, "title": snapshot.title, "group_name": group.name if group else "Компания", "starts_at": plan.starts_at.isoformat(), "timezone": group.timezone_name if group else "UTC"}, key=f"OFFER:{offer.id}")
    responders = [offer for offer in statuses.values() if offer.status in {"ACCEPTED", "WAITING_CONDITION"}]
    count = len(responders)
    plan.required_max_people = effective_capacity(session, plan)
    if eligible:
        plan.required_min_people = min(candidate.intent.min_people for candidate in eligible)
    if count >= plan.required_min_people and all(
        eligible_by_user[offer.user_id].intent.min_people <= count <= (eligible_by_user[offer.user_id].intent.max_people or group_capacity(session, plan.group_id))
        for offer in responders if offer.user_id in eligible_by_user
    ) and all(offer.user_id in eligible_by_user for offer in responders):
        for offer in responders:
            offer.status = "ACCEPTED"
            group = session.get(Group, plan.group_id)
            _enqueue(session, kind="CONFIRMED_PLAN", user_id=offer.user_id, payload={"plan_id": plan.id, "title": snapshot.title, "group_name": group.name if group else "Компания", "starts_at": plan.starts_at.isoformat(), "timezone": group.timezone_name if group else "UTC"}, key=f"CONFIRMED_PLAN:{plan.id}:{offer.user_id}")
        plan.status = "CONFIRMED" if count >= plan.required_max_people else "CONFIRMED_OPEN"
    elif candidate_count(session, plan.id) < plan.required_min_people:
        plan.status = "COLLECTING"
    return True


def regenerate_group(session: Session, group_id: str, city: str, items: list[NormalizedLeisureItem]) -> list[CandidatePlan]:
    """Create/update plans for provider items and commit the request flow once."""
    cleanup_expired(session)
    intents = _active_intents(session, group_id, city)
    location_ids = {intent.origin_location_id for intent in intents if intent.origin_location_id}
    locations = {location.id: location for location in session.scalars(select(Location).where(Location.id.in_(location_ids)))} if location_ids else {}
    capacity = group_capacity(session, group_id)
    plans: list[CandidatePlan] = []
    used_place_days: set[tuple[str, str]] = set()
    expanded = (slot for source in items for slot in (place_slots(source) if source.item_type == "PLACE" else [source]))
    for item in expanded:
        if item.starts_at - timedelta(minutes=10) <= utcnow():
            continue
        place_day = (item.provider_id, item.starts_at.date().isoformat())
        if item.item_type == "PLACE" and place_day in used_place_days:
            continue
        eligible, _ = _evaluate_item(session, group_id, city, item, intents=intents, locations=locations)
        feasibility = feasible_cohort([GroupSizeCandidate(candidate.intent.user_id, candidate.intent.min_people, candidate.intent.max_people) for candidate in eligible], maximum_size=capacity)
        if feasibility is None:
            continue
        if item.item_type == "PLACE":
            used_place_days.add(place_day)
        plan = session.scalar(select(CandidatePlan).join(CandidatePlanSourceSnapshot).where(CandidatePlan.group_id == group_id, CandidatePlan.status.in_(("COLLECTING", "CONFIRMED_OPEN", "CONFIRMED")), CandidatePlanSourceSnapshot.provider == item.provider, CandidatePlanSourceSnapshot.provider_item_id == item.provider_id, CandidatePlan.starts_at == item.starts_at))
        if plan is None:
            plan = CandidatePlan(group_id=group_id, city_slug=city, starts_at=item.starts_at, ends_at=item.ends_at, estimated_price_min=item.price_min, required_min_people=feasibility.size, required_max_people=capacity, status="COLLECTING", expires_at=item.starts_at - timedelta(minutes=10))
            session.add(plan)
            session.flush()
            session.add(CandidatePlanSourceSnapshot(candidate_plan_id=plan.id, provider=item.provider, provider_item_id=item.provider_id, provider_item_type=item.item_type, title=item.title, category=item.category, venue_name=item.venue_name, starts_at=item.starts_at, ends_at=item.ends_at, latitude=item.latitude, longitude=item.longitude, price_text=item.price_text, parsed_price=item.price_min, source_url=item.source_url, image_url=item.image_url, source_fetched_at=item.source_fetched_at, is_demo=item.is_demo, source_metadata={"categories": item.categories, "price_kind": item.price_kind, "address_text": item.address_text, "opening_hours_unverified": item.opening_hours_unverified, "timetable": item.timetable}))
        recompute_candidate_plan(session, plan, intents=intents, locations=locations)
        plans.append(plan)
    session.commit()
    return plans
