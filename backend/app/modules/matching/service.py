"""Application matching flows backed by stable CandidatePlan source snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CandidatePlan,
    CandidatePlanMember,
    CandidatePlanSourceSnapshot,
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
    overlaps,
    recurring_interval_fits,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


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
    return NormalizedLeisureItem(provider=snapshot.provider, provider_id=snapshot.provider_item_id, item_type=snapshot.provider_item_type, city_slug=city_slug, title=snapshot.title, category=snapshot.category, venue_name=snapshot.venue_name, starts_at=snapshot.starts_at, ends_at=snapshot.ends_at, latitude=snapshot.latitude, longitude=snapshot.longitude, price_text=snapshot.price_text, price_min=snapshot.parsed_price, source_url=snapshot.source_url, image_url=snapshot.image_url, source_fetched_at=snapshot.source_fetched_at, is_demo=snapshot.is_demo)


def _evaluate_item(session: Session, group_id: str, city: str, item: NormalizedLeisureItem) -> tuple[list[EvaluatedCandidate], list[EvaluatedCandidate]]:
    eligible_by_user: dict[str, EvaluatedCandidate] = {}
    unverified_by_user: dict[str, EvaluatedCandidate] = {}
    for intent in _active_intents(session, group_id, city):
        if intent.activity_category not in {item.category, "any", "other"} or not _fits_time(intent, item):
            continue
        location = session.get(Location, intent.origin_location_id) if intent.origin_location_id else None
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
    for plan in session.scalars(select(CandidatePlan).where(CandidatePlan.status == "COLLECTING", CandidatePlan.expires_at <= current)):
        plan.status = "EXPIRED"
        for offer in session.scalars(select(Offer).where(Offer.candidate_plan_id == plan.id, Offer.status == "PENDING")):
            offer.status = "EXPIRED"
    for offer in session.scalars(select(Offer).where(Offer.status == "PENDING", Offer.expires_at <= current)):
        offer.status = "EXPIRED"


def _offer_statuses(session: Session, plan_id: str) -> dict[str, Offer]:
    return {offer.user_id: offer for offer in session.scalars(select(Offer).where(Offer.candidate_plan_id == plan_id))}


def _has_other_overlap(session: Session, *, user_id: str, plan: CandidatePlan) -> bool:
    for offer in session.scalars(select(Offer).where(Offer.user_id == user_id, Offer.status == "ACCEPTED", Offer.candidate_plan_id != plan.id)):
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
    return len(list(session.scalars(select(Offer).where(Offer.candidate_plan_id == plan_id, Offer.status == "ACCEPTED"))))


def recompute_candidate_plan(session: Session, plan: CandidatePlan) -> bool:
    """Refresh a plan from its source snapshot; repeated calls are idempotent."""
    cleanup_expired(session)
    if plan.status != "COLLECTING":
        return False
    snapshot = session.scalar(select(CandidatePlanSourceSnapshot).where(CandidatePlanSourceSnapshot.candidate_plan_id == plan.id))
    if snapshot is None or plan.starts_at >= plan.ends_at:
        plan.status = "CANCELLED"
        return False
    eligible, unverified = _evaluate_item(session, plan.group_id, plan.city_slug, _snapshot_item(snapshot, plan.city_slug))
    statuses = _offer_statuses(session, plan.id)
    for candidate in [*eligible, *unverified]:
        _upsert_member(session, plan.id, candidate)
    eligible_by_user = {candidate.intent.user_id: candidate for candidate in eligible}
    accepted_ids = {user_id for user_id, offer in statuses.items() if offer.status == "ACCEPTED" and user_id in eligible_by_user}
    available = [candidate for candidate in eligible if statuses.get(candidate.intent.user_id) is None or statuses[candidate.intent.user_id].status != "REJECTED"]
    feasible_size: int | None = None
    for size in range(1, 13):
        users = {candidate.intent.user_id for candidate in available if candidate.intent.min_people <= size <= candidate.intent.max_people}
        if accepted_ids <= users and len(users) >= size:
            feasible_size = size
            break
    if feasible_size is None:
        plan.status = "CANCELLED"
        for offer in statuses.values():
            if offer.status == "PENDING":
                offer.status = "INVALIDATED"
        return False
    plan.required_min_people = feasible_size
    plan.required_max_people = feasible_size
    supported = [candidate for candidate in available if candidate.intent.min_people <= feasible_size <= candidate.intent.max_people]
    accepted_ranked = sorted((eligible_by_user[user_id] for user_id in accepted_ids), key=lambda candidate: candidate.intent.user_id)
    remaining = sorted((candidate for candidate in supported if candidate.intent.user_id not in accepted_ids), key=EvaluatedCandidate.rank)
    selected = accepted_ranked + remaining[:feasible_size - len(accepted_ranked)]
    selected_ids = {candidate.intent.user_id for candidate in selected}
    for user_id, offer in statuses.items():
        if offer.status == "PENDING" and (user_id not in selected_ids or _has_other_overlap(session, user_id=user_id, plan=plan)):
            offer.status = "INVALIDATED"
    for candidate in selected:
        current = statuses.get(candidate.intent.user_id)
        if current is None:
            offer = Offer(candidate_plan_id=plan.id, user_id=candidate.intent.user_id, status="PENDING", is_near=candidate.kind == "NEAR", expires_at=plan.expires_at)
            session.add(offer)
            session.flush()
            _enqueue(session, kind="OFFER", user_id=candidate.intent.user_id, payload={"candidate_plan_id": plan.id}, key=f"OFFER:{offer.id}")
    if candidate_count(session, plan.id) == feasible_size:
        plan.status = "CONFIRMED"
        for offer in session.scalars(select(Offer).where(Offer.candidate_plan_id == plan.id, Offer.status == "ACCEPTED")):
            _enqueue(session, kind="CONFIRMED_PLAN", user_id=offer.user_id, payload={"plan_id": plan.id, "title": snapshot.title}, key=f"CONFIRMED_PLAN:{plan.id}:{offer.user_id}")
    return True


def regenerate_group(session: Session, group_id: str, city: str, items: list[NormalizedLeisureItem]) -> list[CandidatePlan]:
    """Create/update plans for provider items and commit the request flow once."""
    cleanup_expired(session)
    plans: list[CandidatePlan] = []
    for item in items:
        eligible, _ = _evaluate_item(session, group_id, city, item)
        feasibility = feasible_cohort([GroupSizeCandidate(candidate.intent.user_id, candidate.intent.min_people, candidate.intent.max_people) for candidate in eligible])
        if feasibility is None:
            continue
        plan = session.scalar(select(CandidatePlan).join(CandidatePlanSourceSnapshot).where(CandidatePlan.group_id == group_id, CandidatePlan.status == "COLLECTING", CandidatePlanSourceSnapshot.provider == item.provider, CandidatePlanSourceSnapshot.provider_item_id == item.provider_id))
        if plan is None:
            plan = CandidatePlan(group_id=group_id, city_slug=city, starts_at=item.starts_at, ends_at=item.ends_at, estimated_price_min=item.price_min, required_min_people=feasibility.size, required_max_people=feasibility.size, status="COLLECTING", expires_at=min(item.starts_at, utcnow() + timedelta(hours=24)))
            session.add(plan)
            session.flush()
            session.add(CandidatePlanSourceSnapshot(candidate_plan_id=plan.id, provider=item.provider, provider_item_id=item.provider_id, provider_item_type=item.item_type, title=item.title, category=item.category, venue_name=item.venue_name, starts_at=item.starts_at, ends_at=item.ends_at, latitude=item.latitude, longitude=item.longitude, price_text=item.price_text, parsed_price=item.price_min, source_url=item.source_url, image_url=item.image_url, source_fetched_at=item.source_fetched_at, is_demo=item.is_demo))
        recompute_candidate_plan(session, plan)
        plans.append(plan)
    session.commit()
    return plans
