from __future__ import annotations

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
from app.modules.matching.domain import compatibility, overlaps


def utcnow() -> datetime:
    return datetime.now(UTC)


def _active_intents(session: Session, group_id: str, city: str) -> list[Intent]:
    current = utcnow()
    intents = list(
        session.scalars(
            select(Intent).where(
                Intent.group_id == group_id, Intent.status == "ACTIVE", Intent.city_slug == city
            )
        )
    )
    return [
        intent for intent in intents if intent.expires_at is None or intent.expires_at > current
    ]


def _fits_time(intent: Intent, item: NormalizedLeisureItem) -> bool:
    if intent.type == "RECURRING":
        recurrence = intent.recurrence_json or {}
        weekdays = recurrence.get("weekdays", [])
        return int(item.starts_at.weekday()) in weekdays
    return (
        intent.available_from is not None
        and intent.available_to is not None
        and overlaps(intent.available_from, intent.available_to, item.starts_at, item.ends_at)
    )


def regenerate_group(
    session: Session, group_id: str, city: str, items: list[NormalizedLeisureItem]
) -> list[CandidatePlan]:
    intents = _active_intents(session, group_id, city)
    plans: list[CandidatePlan] = []
    for item in items:
        available = [
            intent
            for intent in intents
            if intent.activity_category in {item.category, "any", "other"}
            and _fits_time(intent, item)
        ]
        if not available:
            continue
        leader = available[0]
        plan = session.scalar(
            select(CandidatePlan).where(
                CandidatePlan.group_id == group_id,
                CandidatePlan.status == "COLLECTING",
                CandidatePlan.id.in_(
                    select(CandidatePlanSourceSnapshot.candidate_plan_id).where(
                        CandidatePlanSourceSnapshot.provider == item.provider,
                        CandidatePlanSourceSnapshot.provider_item_id == item.provider_id,
                    )
                ),
            )
        )
        if plan is None:
            plan = CandidatePlan(
                group_id=group_id,
                city_slug=city,
                starts_at=item.starts_at,
                ends_at=item.ends_at,
                estimated_price_min=item.price_min,
                required_min_people=leader.min_people,
                required_max_people=leader.max_people,
                status="COLLECTING",
                expires_at=min(item.starts_at, utcnow() + timedelta(hours=24)),
            )
            session.add(plan)
            session.flush()
            session.add(
                CandidatePlanSourceSnapshot(
                    candidate_plan_id=plan.id,
                    provider=item.provider,
                    provider_item_id=item.provider_id,
                    provider_item_type=item.item_type,
                    title=item.title,
                    category=item.category,
                    venue_name=item.venue_name,
                    starts_at=item.starts_at,
                    ends_at=item.ends_at,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    price_text=item.price_text,
                    parsed_price=item.price_min,
                    source_url=item.source_url,
                    image_url=item.image_url,
                    source_fetched_at=item.source_fetched_at,
                    is_demo=item.is_demo,
                )
            )
        if plan.required_min_people > plan.required_max_people:
            continue
        existing_users = {
            row.user_id
            for row in session.scalars(
                select(CandidatePlanMember).where(CandidatePlanMember.candidate_plan_id == plan.id)
            )
        }
        candidates: list[tuple[Intent, str, float, int | None]] = []
        for intent in available:
            location = session.get(Location, intent.origin_location_id)
            if location is None or item.latitude is None or item.longitude is None:
                continue
            from app.modules.matching.domain import haversine_km

            distance = haversine_km(
                location.latitude, location.longitude, item.latitude, item.longitude
            )
            result = compatibility(
                price=item.price_min,
                max_budget=intent.budget_max,
                near_limit=settings.near_budget_max_delta_rub,
                distance_km=distance,
                radius_km=intent.radius_km,
            )
            if (
                result.kind != "CONFLICT"
                and intent.min_people <= plan.required_max_people
                and intent.max_people >= plan.required_min_people
            ):
                candidates.append((intent, result.kind, distance, result.budget_delta))
        candidates.sort(
            key=lambda item: (item[1] == "NEAR", item[2], item[0].created_at, item[0].user_id)
        )
        for intent, kind, distance, delta in candidates[: plan.required_max_people]:
            if intent.user_id in existing_users:
                continue
            deviation = {"type": "BUDGET_OVER_MAX", "delta": delta} if kind == "NEAR" else None
            session.add(
                CandidatePlanMember(
                    candidate_plan_id=plan.id,
                    user_id=intent.user_id,
                    intent_id=intent.id,
                    compatibility=kind,
                    distance_km=round(distance, 1),
                    budget_delta=delta,
                    deviations_json=deviation,
                )
            )
            session.add(
                Offer(
                    candidate_plan_id=plan.id,
                    user_id=intent.user_id,
                    status="PENDING",
                    is_near=kind == "NEAR",
                    expires_at=plan.expires_at,
                )
            )
            session.add(
                OutboxNotification(
                    kind="OFFER", user_id=intent.user_id, payload={"candidate_plan_id": plan.id}
                )
            )
        plans.append(plan)
    session.commit()
    return plans


def candidate_count(session: Session, plan_id: str) -> int:
    return len(
        list(
            session.scalars(
                select(Offer).where(Offer.candidate_plan_id == plan_id, Offer.status == "ACCEPTED")
            )
        )
    )
