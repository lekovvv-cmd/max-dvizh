"""Periodic AutoSignal evaluation with a PostgreSQL advisory lock."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from time import monotonic, sleep

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CandidatePlanMember, DvizhSession, Intent, Offer, User
from app.db.session import SessionLocal, engine
from app.modules.leisure.provider import ProviderQuery, fetch_items
from app.modules.matching.dvizh import recompute as recompute_dvizh
from app.modules.matching.service import regenerate_group

logger = logging.getLogger(__name__)
LOCK_ID = 564836421


def evaluate_active_autosignals(session: Session, current: datetime | None = None) -> int:
    """Fetch each city/category slice once, then match every relevant company."""
    current = current or datetime.now(UTC)
    active = list(
        session.scalars(
            select(Intent).where(
                Intent.type == "RECURRING", Intent.status == "ACTIVE", Intent.flow_version == 1
            )
        )
    )
    slices: dict[tuple[str, tuple[str, ...]], set[str]] = {}
    for intent in active:
        categories = tuple(
            sorted(
                category
                for category in (intent.activity_categories or [intent.activity_category])
                if category not in {"any", "other"}
            )
        )
        slices.setdefault((intent.city_slug, categories), set()).add(intent.group_id)
    refreshed = 0
    for (city, categories), groups in slices.items():
        query = ProviderQuery(
            city_slug=city,
            starts_at=current,
            ends_at=current + timedelta(days=settings.autosignal_lookahead_days),
            categories=categories,
        )
        result = fetch_items(query)
        if result.unavailable:
            logger.warning("AutoSignal provider unavailable for city %s", city)
            for intent in active:
                if (
                    intent.city_slug == city
                    and tuple(
                        sorted(
                            category
                            for category in (
                                intent.activity_categories or [intent.activity_category]
                            )
                            if category not in {"any", "other"}
                        )
                    )
                    == categories
                ):
                    intent.provider_state = "PROVIDER_UNAVAILABLE"
            session.commit()
            continue
        for group_id in sorted(groups):
            regenerate_group(session, group_id, city, result.items)
            refreshed += 1
        for intent in active:
            if (
                intent.city_slug == city
                and tuple(
                    sorted(
                        category
                        for category in (intent.activity_categories or [intent.activity_category])
                        if category not in {"any", "other"}
                    )
                )
                == categories
            ):
                visible = session.scalar(
                    select(Offer.id)
                    .join(
                        CandidatePlanMember,
                        CandidatePlanMember.candidate_plan_id == Offer.candidate_plan_id,
                    )
                    .where(
                        CandidatePlanMember.intent_id == intent.id,
                        Offer.user_id == intent.user_id,
                        Offer.status.in_(
                            ("PENDING", "ACCEPTED", "WAITING_CONDITION", "WAITLISTED")
                        ),
                    )
                    .limit(1)
                )
                intent.provider_state = (
                    "OFFERS_READY"
                    if visible
                    else "NO_FEASIBLE_PLAN"
                    if result.items
                    else "NO_SOURCE"
                )
        session.commit()
    return refreshed


def evaluate_auto_signal(intent_id: str) -> None:
    """Evaluate a changed rule after the HTTP response using its own session."""
    try:
        with SessionLocal() as session:
            intent = session.get(Intent, intent_id)
            if (
                intent is None
                or intent.type != "RECURRING"
                or intent.status != "ACTIVE"
                or intent.flow_version != 1
            ):
                return
            categories = tuple(
                sorted(
                    category
                    for category in (intent.activity_categories or [intent.activity_category])
                    if category not in {"any", "other"}
                )
            )
            current = datetime.now(UTC)
            query = ProviderQuery(
                city_slug=intent.city_slug,
                starts_at=current,
                ends_at=current + timedelta(days=settings.autosignal_lookahead_days),
                categories=categories,
            )
            result = fetch_items(query)
            if result.unavailable:
                intent.provider_state = "PROVIDER_UNAVAILABLE"
            else:
                regenerate_group(session, intent.group_id, intent.city_slug, result.items)
                visible = session.scalar(
                    select(Offer.id)
                    .join(
                        CandidatePlanMember,
                        CandidatePlanMember.candidate_plan_id == Offer.candidate_plan_id,
                    )
                    .where(
                        CandidatePlanMember.intent_id == intent.id,
                        Offer.user_id == intent.user_id,
                        Offer.status.in_(
                            ("PENDING", "ACCEPTED", "WAITING_CONDITION", "WAITLISTED")
                        ),
                    )
                    .limit(1)
                )
                intent.provider_state = (
                    "OFFERS_READY"
                    if visible
                    else "NO_FEASIBLE_PLAN"
                    if result.items
                    else "NO_SOURCE"
                )
            session.commit()
    except Exception:
        logger.exception("AutoSignal evaluation failed for %s", intent_id)


def run_once() -> int:
    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": LOCK_ID}
        )
        # Advisory locks are session-scoped. End the implicit SELECT transaction so
        # the bound Session can commit its own state changes instead of joining it.
        connection.commit()
        if not acquired:
            return 0
        try:
            with Session(bind=connection) as session:
                refreshed = evaluate_active_autosignals(session) if settings.local_demo_mode else 0
                from app.api.routes.dvizh import materialize_recurring

                for rule in list(
                    session.scalars(
                        select(Intent).where(
                            Intent.type == "RECURRING",
                            Intent.flow_version == 2,
                            Intent.status == "ACTIVE",
                        )
                    )
                ):
                    user = session.get(User, rule.user_id)
                    if user:
                        materialize_recurring(session, rule, user)
                for dvizh in session.scalars(
                    select(DvizhSession)
                    .where(
                        DvizhSession.status.in_(
                            (
                                "CHOOSING_CANDIDATES",
                                "NO_SOURCE",
                                "PROVIDER_UNAVAILABLE",
                                "COLLECTING_REACTIONS",
                                "AWAITING_CONFIRMATION",
                            )
                        )
                    )
                    .with_for_update(skip_locked=True)
                ):
                    recompute_dvizh(session, dvizh)
                session.commit()
                connection.commit()
                return refreshed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": LOCK_ID})
            connection.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    while True:
        started = monotonic()
        try:
            logger.info("AutoSignal scheduler refreshed %s companies", run_once())
        except Exception:
            logger.exception("AutoSignal scheduler run failed")
        interval = max(60, settings.autosignal_poll_seconds)
        sleep(max(1, interval - (monotonic() - started)))


if __name__ == "__main__":
    main()
