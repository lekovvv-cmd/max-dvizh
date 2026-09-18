"""End-to-end domain/API regressions for open plans and Signal batches."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes import product
from app.api.schemas import AutoSignalIn, OfferAction, SignalBatchIn
from app.core.config import settings
from app.core.timezones import display_timezone
from app.db.models import (
    Base,
    CandidatePlan,
    CandidatePlanSourceSnapshot,
    Group,
    GroupMember,
    Intent,
    Offer,
    User,
)
from app.modules.leisure.provider import NormalizedLeisureItem, ProviderResult
from app.modules.matching import scheduler
from app.modules.matching.domain import offer_expiry
from app.modules.matching.scheduler import evaluate_active_autosignals
from app.modules.matching.service import regenerate_group
from app.modules.max_integration.client import _text


def seed(session: Session, count: int, minimums: list[int], maximum: int | None = None) -> tuple[list[User], Group, NormalizedLeisureItem]:
    current = datetime.now(UTC)
    users = [User(id=f"user-{index}", max_user_id=f"max-{index}", display_name=f"User {index}") for index in range(count)]
    group = Group(id="group", name="Друзья", default_city_slug="ekb", created_by=users[0].id, invite_token="invite")
    session.add_all([*users, group])
    session.flush()
    for index, user in enumerate(users):
        session.add(GroupMember(group_id=group.id, user_id=user.id))
        session.add(Intent(user_id=user.id, group_id=group.id, type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="any", activity_categories=["any"], available_from=current, available_to=current + timedelta(hours=6), min_people=minimums[index], max_people=maximum))
    session.commit()
    item = NormalizedLeisureItem(provider="MODEL", provider_id="demo", item_type="EVENT", city_slug="ekb", title="Квиз", category="games", venue_name="Клуб", starts_at=current + timedelta(hours=2), ends_at=current + timedelta(hours=4), latitude=None, longitude=None, price_text=None, price_min=None, source_url=None, image_url=None, source_fetched_at=current, is_demo=True)
    return users, group, item


def test_all_eight_get_offers_and_plan_stays_open_after_three_responses() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 8, [3] * 8)
        plan = regenerate_group(session, group.id, "ekb", [item])[0]
        offers = {offer.user_id: offer for offer in session.scalars(select(Offer))}
        assert len(offers) == 8
        for user in users[:3]:
            product.accept_offer(offers[user.id].id, OfferAction(), session, SimpleNamespace(id=user.id))
        assert plan.status == "CONFIRMED_OPEN"
        assert product.offer_out(session, offers[users[3].id]).remaining_capacity == 5
        for user in users[3:]:
            product.accept_offer(offers[user.id].id, OfferAction(), session, SimpleNamespace(id=user.id))
        assert plan.status == "CONFIRMED"
        assert len(list(session.scalars(select(Offer).where(Offer.status == "ACCEPTED")))) == 8


def test_first_eligible_member_gets_offer_before_minimum_signals_exist() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users = [User(id=f"early-{index}", max_user_id=f"early-{index}", display_name=f"Early {index}") for index in range(5)]
        group = Group(id="early-group", name="Friends", default_city_slug="ekb", created_by=users[0].id)
        session.add_all([*users, group])
        session.flush()
        session.add_all(GroupMember(group_id=group.id, user_id=user.id) for user in users)
        current = datetime.now(UTC)
        session.add(Intent(user_id=users[0].id, group_id=group.id, type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="games", available_from=current, available_to=current + timedelta(hours=6), min_people=3))
        session.commit()
        item = NormalizedLeisureItem(provider="MODEL", provider_id="first", item_type="EVENT", city_slug="ekb", title="Квиз", category="games", venue_name="Клуб", starts_at=current + timedelta(hours=2), ends_at=current + timedelta(hours=4), latitude=None, longitude=None, price_text=None, price_min=None, source_url=None, image_url=None, source_fetched_at=current, is_demo=True)
        plans = regenerate_group(session, group.id, "ekb", [item])
        assert len(plans) == 1
        assert plans[0].status == "COLLECTING"
        assert plans[0].required_min_people == 3
        assert len(list(session.scalars(select(Offer)))) == 1
        assert len(list(session.scalars(select(CandidatePlanSourceSnapshot)))) == 1
        assert len(list(session.scalars(select(CandidatePlan)))) == 1


def test_exact_five_waitlist_promotes_first_responder_after_cancellation() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 7, [5] * 7, maximum=5)
        plan = regenerate_group(session, group.id, "ekb", [item])[0]
        offers = {offer.user_id: offer for offer in session.scalars(select(Offer))}
        for user in users[:7]:
            product.accept_offer(offers[user.id].id, OfferAction(), session, SimpleNamespace(id=user.id))
        assert plan.status == "CONFIRMED"
        assert [offers[user.id].status for user in users[5:]] == ["WAITLISTED", "WAITLISTED"]
        product.cancel_accepted_offer(offers[users[0].id].id, session, SimpleNamespace(id=users[0].id))
        assert offers[users[5].id].status == "ACCEPTED"
        assert offers[users[6].id].status == "WAITLISTED"
        assert plan.status == "CONFIRMED"


def test_mixed_minimums_confirm_only_when_every_responder_allows_final_size() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 5, [2, 5, 2, 3, 5])
        plan = regenerate_group(session, group.id, "ekb", [item])[0]
        offers = {offer.user_id: offer for offer in session.scalars(select(Offer))}
        for user in users[:4]:
            product.accept_offer(offers[user.id].id, OfferAction(), session, SimpleNamespace(id=user.id))
        assert plan.status == "COLLECTING"
        product.accept_offer(offers[users[4].id].id, OfferAction(), session, SimpleNamespace(id=users[4].id))
        assert plan.status == "CONFIRMED"
        assert all(offer.status == "ACCEPTED" for offer in offers.values())


def test_dynamic_offer_ttl() -> None:
    current = datetime(2026, 9, 18, tzinfo=UTC)
    assert offer_expiry(current, current + timedelta(hours=2)) == current + timedelta(hours=1)
    assert offer_expiry(current, current + timedelta(hours=6)) == current + timedelta(hours=3)
    assert offer_expiry(current, current + timedelta(hours=24)) == current + timedelta(hours=6)
    assert offer_expiry(current, current + timedelta(minutes=9)) is None


def test_company_share_timezone_accepts_kudago_gmt_offsets_and_iana() -> None:
    current = datetime(2026, 9, 18, 16, 0, tzinfo=UTC)
    assert current.astimezone(display_timezone("GMT+03:00")).hour == 19
    assert current.astimezone(display_timezone("Asia/Yekaterinburg")).hour == 21
    notification = SimpleNamespace(kind="OFFER", payload={"title": "Квиз", "group_name": "Друзья", "starts_at": current.isoformat(), "timezone": "GMT+03:00"})
    assert "19:00" in _text(notification)


def test_collecting_response_keeps_overlapping_offer_invalidated() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 2, [2, 2])
        plans = regenerate_group(session, group.id, "ekb", [item, replace(item, provider_id="other", title="Другое")])
        selected = session.scalar(select(Offer).where(Offer.candidate_plan_id == plans[0].id, Offer.user_id == users[0].id))
        competing = session.scalar(select(Offer).where(Offer.candidate_plan_id == plans[1].id, Offer.user_id == users[0].id))
        assert selected is not None and competing is not None
        product.accept_offer(selected.id, OfferAction(), session, users[0])
        assert selected.status == "WAITING_CONDITION"
        assert competing.status == "INVALIDATED"


def test_signal_batch_rejects_mixed_cities_without_partial_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id="user", max_user_id="user", display_name="User")
        first = Group(id="first", name="A", default_city_slug="ekb", created_by=user.id)
        second = Group(id="second", name="B", default_city_slug="msk", created_by=user.id)
        session.add_all([user, first, second, GroupMember(group_id=first.id, user_id=user.id), GroupMember(group_id=second.id, user_id=user.id)])
        session.commit()
        current = datetime.now(UTC)
        payload = SignalBatchIn(group_ids=[first.id, second.id], available_from=current + timedelta(hours=1), available_to=current + timedelta(hours=4))
        monkeypatch.setattr(product, "fetch_items", lambda *_: ProviderResult([], False, current))
        with pytest.raises(HTTPException) as failure:
            product.create_signal_batch(payload, session, user)
        assert failure.value.status_code == 422
        assert list(session.scalars(select(Intent))) == []


def test_scheduler_uses_active_recurring_rules_without_visiting_app(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id="scheduled-user", max_user_id="scheduled-user", display_name="User")
        group = Group(id="scheduled-group", name="A", default_city_slug="ekb", created_by=user.id)
        session.add_all([user, group, GroupMember(group_id=group.id, user_id=user.id)])
        session.add(Intent(user_id=user.id, group_id=group.id, type="RECURRING", status="ACTIVE", city_slug="ekb", activity_category="games", activity_categories=["games"], min_people=2, max_people=None))
        session.commit()
        queries = []
        refreshed = []
        monkeypatch.setattr("app.modules.matching.scheduler.fetch_items", lambda query: (queries.append(query), ProviderResult([], False, datetime.now(UTC)))[1])
        monkeypatch.setattr("app.modules.matching.scheduler.regenerate_group", lambda _session, group_id, city, items: refreshed.append((group_id, city, items)))
        assert evaluate_active_autosignals(session) == 1
        assert [(query.city_slug, query.categories) for query in queries] == [("ekb", ("games",))]
        assert refreshed == [(group.id, "ekb", [])]


def test_scheduler_poll_interval_includes_evaluation_time(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter((100.0, 125.0))
    monkeypatch.setattr(scheduler, "settings", replace(settings, autosignal_poll_seconds=1800))
    monkeypatch.setattr(scheduler, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(scheduler, "run_once", lambda: 1)
    observed: list[float] = []

    def stop_after_sleep(delay: float) -> None:
        observed.append(delay)
        raise StopIteration

    monkeypatch.setattr(scheduler, "sleep", stop_after_sleep)
    with pytest.raises(StopIteration):
        scheduler.main()
    assert observed == [1775.0]


def test_auto_signal_save_returns_before_provider_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id="auto-user", max_user_id="auto-user", display_name="User")
        group = Group(id="auto-group", name="Friends", default_city_slug="ekb", created_by=user.id)
        session.add_all([user, group, GroupMember(group_id=group.id, user_id=user.id)])
        session.commit()
        monkeypatch.setattr(product, "fetch_items", lambda *_: pytest.fail("provider must run after response"))
        tasks = BackgroundTasks()
        payload = AutoSignalIn(group_id=group.id, name="Friday", weekdays=[4], local_start="18:00", local_end="23:00", timezone="Asia/Yekaterinburg", min_people=2)
        created = product.create_auto_signal(payload, tasks, session, user)
        assert created.status == "ACTIVE"
        assert session.get(Intent, created.id) is not None
        assert len(tasks.tasks) == 1
        assert tasks.tasks[0].args == (created.id,)


def test_join_distinguishes_invalid_and_expired_invitations() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id="owner", max_user_id="owner", display_name="Owner")
        visitor = User(id="visitor", max_user_id="visitor", display_name="Visitor")
        group = Group(id="invite-group", name="Friends", default_city_slug="ekb", created_by=user.id, invite_token="real-token", invite_expires_at=datetime.now(UTC) - timedelta(minutes=1))
        session.add_all([user, visitor, group])
        session.commit()
        with pytest.raises(HTTPException) as expired:
            product.join_group("real-token", session, visitor)
        with pytest.raises(HTTPException) as invalid:
            product.join_group("wrong-token", session, visitor)
        assert expired.value.status_code == 410
        assert invalid.value.status_code == 404


def test_signal_batch_persists_provider_outage_and_owner_can_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id="signal-user", max_user_id="signal-user", display_name="User")
        group = Group(id="signal-group", name="Friends", default_city_slug="ekb", created_by=user.id)
        session.add_all([user, group, GroupMember(group_id=group.id, user_id=user.id)])
        session.commit()
        current = datetime.now(UTC)
        payload = SignalBatchIn(group_ids=[group.id], available_from=current + timedelta(hours=1), available_to=current + timedelta(hours=4))
        monkeypatch.setattr(product, "fetch_items", lambda *_: ProviderResult([], False, current, unavailable=True))
        created = product.create_signal_batch(payload, session, user)
        assert created.intents[0].provider_state == "PROVIDER_UNAVAILABLE"
        monkeypatch.setattr(product, "fetch_items", lambda *_: ProviderResult([], False, current))
        refreshed = product.refresh_signal_batch(created.signal_batch_id, session, user)
        assert refreshed.intents[0].provider_state == "NO_SOURCE"
