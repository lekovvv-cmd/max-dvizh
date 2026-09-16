"""Real PostgreSQL regression coverage for locking, recompute and outbox claims."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier, Thread
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.product import accept_offer, reject_offer
from app.api.schemas import OfferAction
from app.core.config import settings
from app.db.models import (
    Base,
    CandidatePlan,
    CandidatePlanMember,
    CandidatePlanSourceSnapshot,
    Group,
    GroupMember,
    Intent,
    Offer,
    OutboxNotification,
    User,
)
from app.modules.matching.service import recompute_candidate_plan
from app.modules.max_integration import client as outbox_client

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is required: PostgreSQL reliability tests must not be skipped")


@pytest.fixture
def engine() -> Engine:
    database = create_engine(TEST_DATABASE_URL, pool_size=8, max_overflow=0)
    Base.metadata.drop_all(database)
    Base.metadata.create_all(database)
    yield database
    Base.metadata.drop_all(database)
    database.dispose()


def seed_plan(session: Session, users: list[User], plan_id: str, start: datetime, required: int = 1) -> list[Offer]:
    group = session.get(Group, "group")
    if group is None:
        group = Group(id="group", name="Друзья", default_city_slug="ekb", created_by=users[0].id, invite_token="invite")
        session.add(group)
        session.flush()
    plan = CandidatePlan(id=plan_id, group_id="group", city_slug="ekb", starts_at=start, ends_at=start + timedelta(hours=2), estimated_price_min=400, required_min_people=required, required_max_people=required, status="COLLECTING", expires_at=start + timedelta(hours=1))
    session.add(plan)
    session.add(CandidatePlanSourceSnapshot(candidate_plan_id=plan.id, provider="MODEL", provider_item_id=plan_id, provider_item_type="MODEL", title=plan_id, category="other", venue_name=None, starts_at=plan.starts_at, ends_at=plan.ends_at, latitude=None, longitude=None, price_text="400 ₽", parsed_price=400, source_url=None, image_url=None, source_fetched_at=start, is_demo=True))
    offers: list[Offer] = []
    for user in users:
        if session.scalar(
            select(GroupMember).where(GroupMember.group_id == "group", GroupMember.user_id == user.id)
        ) is None:
            session.add(GroupMember(group_id="group", user_id=user.id))
        intent = Intent(id=f"intent-{plan_id}-{user.id}", user_id=user.id, group_id="group", type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="other", available_from=start - timedelta(hours=1), available_to=start + timedelta(hours=3), budget_max=None, origin_location_id=None, radius_km=None, min_people=required, max_people=required)
        session.add(intent)
        session.flush()
        session.add(CandidatePlanMember(candidate_plan_id=plan.id, user_id=user.id, intent_id=intent.id, compatibility="EXACT", distance_km=None, budget_delta=None, deviations_json=None))
        offer = Offer(candidate_plan_id=plan.id, user_id=user.id, status="PENDING", is_near=False, expires_at=plan.expires_at)
        session.add(offer)
        offers.append(offer)
    session.commit()
    return offers


def users(session: Session, count: int) -> list[User]:
    result = [User(id=f"user-{index}", max_user_id=f"max-{index}", display_name=f"U{index}") for index in range(count)]
    session.add_all(result)
    session.commit()
    return result


def test_last_slot_and_same_user_overlap_are_atomic(engine: Engine) -> None:
    start = datetime.now(UTC) + timedelta(hours=2)
    with Session(engine) as session:
        people = users(session, 2)
        people_ids = [person.id for person in people]
        offer_ids = [offer.id for offer in seed_plan(session, people, "one", start)]
    barrier = Barrier(2)
    outcomes: list[int] = []

    def accept(offer_id: str, user_id: str) -> None:
        with Session(engine) as session:
            barrier.wait()
            try:
                accept_offer(offer_id, OfferAction(), session, SimpleNamespace(id=user_id))
                outcomes.append(200)
            except HTTPException as error:
                outcomes.append(error.status_code)

    threads = [Thread(target=accept, args=(offer_id, person_id)) for offer_id, person_id in zip(offer_ids, people_ids, strict=True)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    with Session(engine) as session:
        assert len(list(session.scalars(select(Offer).where(Offer.status == "ACCEPTED")))) == 1
        assert session.get(CandidatePlan, "one").status == "CONFIRMED"  # type: ignore[union-attr]
    assert sorted(outcomes) == [200, 409]

    with Session(engine) as session:
        solo = User(id="solo", max_user_id="max-solo", display_name="Solo")
        session.add(solo)
        session.commit()
        solo_id = solo.id
        both_ids = [
            *(offer.id for offer in seed_plan(session, [solo], "two-a", start + timedelta(hours=4))),
            *(offer.id for offer in seed_plan(session, [solo], "two-b", start + timedelta(hours=5))),
        ]
    barrier = Barrier(2)
    outcomes = []
    threads = [Thread(target=accept, args=(offer_id, solo_id)) for offer_id in both_ids]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    with Session(engine) as session:
        accepted = list(session.scalars(select(Offer).where(Offer.user_id == solo_id, Offer.status == "ACCEPTED")))
        assert len(accepted) == 1
    assert sorted(outcomes) == [200, 409]


def test_reject_recompute_promotes_reserve_once_and_never_reoffers_rejected(engine: Engine) -> None:
    start = datetime.now(UTC) + timedelta(hours=2)
    with Session(engine) as session:
        people = users(session, 3)
        offers = seed_plan(session, people[:2], "reserve", start, required=2)
        reserve_intent = Intent(id="intent-reserve-user-2", user_id=people[2].id, group_id="group", type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="other", available_from=start - timedelta(hours=1), available_to=start + timedelta(hours=3), budget_max=None, origin_location_id=None, radius_km=None, min_people=2, max_people=2)
        session.add(reserve_intent)
        session.commit()
        rejected = reject_offer(offers[0].id, session, people[0])
        assert rejected.status == "REJECTED"
        plan = session.get(CandidatePlan, "reserve")
        assert plan is not None
        recompute_candidate_plan(session, plan)
        recompute_candidate_plan(session, plan)
        session.commit()
        statuses = {offer.user_id: offer.status for offer in session.scalars(select(Offer).where(Offer.candidate_plan_id == "reserve"))}
        assert statuses[people[0].id] == "REJECTED"
        assert statuses[people[2].id] == "PENDING"
        assert session.query(OutboxNotification).count() == 1


def test_outbox_claim_retry_stale_and_dedupe_on_postgres(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbox_client, "settings", replace(settings, max_bot_token="token"))
    monkeypatch.setattr(outbox_client, "send_bot_message", lambda *_: True)
    with Session(engine) as session:
        person = users(session, 1)[0]
        event = OutboxNotification(kind="OFFER", user_id=person.id, payload={}, status="PENDING", dedupe_key="one")
        session.add(event)
        session.commit()
        assert outbox_client.dispatch_pending(session) == 1
        assert event.status == "SENT"
        duplicate = OutboxNotification(kind="OFFER", user_id=person.id, payload={}, status="PENDING", dedupe_key="one")
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        event.status = "PROCESSING"
        event.locked_at = datetime.now(UTC) - timedelta(minutes=6)
        session.commit()
        assert outbox_client.dispatch_pending(session) == 1
        assert event.status == "SENT"
        failing = OutboxNotification(kind="OFFER", user_id=person.id, payload={}, status="PENDING", dedupe_key="failure")
        session.add(failing)
        session.commit()
        monkeypatch.setattr(outbox_client, "send_bot_message", lambda *_: (_ for _ in ()).throw(httpx.ConnectError("down")))
        assert outbox_client.dispatch_pending(session) == 0
        assert failing.status == "PENDING" and failing.attempts == 1 and failing.next_attempt_at is not None
        before = failing.status, failing.attempts
        monkeypatch.setattr(outbox_client, "settings", replace(settings, max_bot_token=""))
        assert outbox_client.dispatch_pending(session) == 0
        assert (failing.status, failing.attempts) == before
