"""End-to-end domain/API regressions for open plans and Signal batches."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes import product
from app.api.schemas import (
    AutoSignalIn,
    GroupCityUpdateIn,
    LocationIn,
    LocationRenameIn,
    OfferAction,
    SignalBatchIn,
)
from app.core.config import settings
from app.core.timezones import display_timezone
from app.db.models import (
    Base,
    CandidatePlan,
    CandidatePlanSourceSnapshot,
    Group,
    GroupMember,
    Intent,
    Location,
    Offer,
    OutboxNotification,
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
        assert product.offer_out(session, offers[users[5].id]).can_waitlist is True
        product.cancel_accepted_offer(offers[users[0].id].id, session, SimpleNamespace(id=users[0].id))
        assert offers[users[5].id].status == "ACCEPTED"
        assert offers[users[6].id].status == "WAITLISTED"
        assert plan.status == "CONFIRMED"


def test_mixed_minimums_preserve_confirmed_core_and_promote_conditional_member() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 5, [2, 2, 5, 2, 2])
        plan = regenerate_group(session, group.id, "ekb", [item])[0]
        offers = {offer.user_id: offer for offer in session.scalars(select(Offer))}
        for user in users[:2]:
            product.accept_offer(offers[user.id].id, OfferAction(), session, SimpleNamespace(id=user.id))
        assert plan.status == "CONFIRMED_OPEN"
        product.accept_offer(offers[users[2].id].id, OfferAction(), session, SimpleNamespace(id=users[2].id))
        assert plan.status == "CONFIRMED_OPEN"
        assert [offers[user.id].status for user in users[:3]] == ["ACCEPTED", "ACCEPTED", "WAITING_CONDITION"]
        ordinary = product.plan_out(session, plan, users[0].id)
        conditional = product.plan_out(session, plan, users[2].id)
        assert (ordinary.participant_count, ordinary.personal_required_min) == (2, None)
        assert (conditional.participant_count, conditional.conditional_count, conditional.personal_response_count, conditional.personal_required_min) == (2, 1, 3, 5)
        assert conditional.share_text == ""
        pending = product.offer_out(session, offers[users[3].id])
        assert (pending.accepted_count, pending.conditional_count, pending.required_min_people) == (2, 1, 2)
        product.accept_offer(offers[users[3].id].id, OfferAction(), session, SimpleNamespace(id=users[3].id))
        assert plan.status == "CONFIRMED_OPEN"
        assert offers[users[2].id].status == "WAITING_CONDITION"
        product.accept_offer(offers[users[4].id].id, OfferAction(), session, SimpleNamespace(id=users[4].id))
        assert plan.status == "CONFIRMED"
        assert all(offer.status == "ACCEPTED" for offer in offers.values())
        product.cancel_accepted_offer(offers[users[4].id].id, session, SimpleNamespace(id=users[4].id))
        assert plan.status == "CONFIRMED_OPEN"
        assert [offers[user.id].status for user in users[:4]] == ["ACCEPTED", "ACCEPTED", "WAITING_CONDITION", "ACCEPTED"]


def test_only_exact_capacity_can_show_waitlist_action() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 4, [2] * 4, maximum=3)
        plan = regenerate_group(session, group.id, "ekb", [item])[0]
        offers = {offer.user_id: offer for offer in session.scalars(select(Offer))}
        for user in users[:3]:
            product.accept_offer(offers[user.id].id, OfferAction(), session, SimpleNamespace(id=user.id))
        full = product.offer_out(session, offers[users[3].id])
        assert plan.status == "CONFIRMED"
        assert (full.remaining_capacity, full.can_waitlist, full.can_accept) == (0, False, False)


def test_exact_waiter_promoted_into_open_core_sets_final_capacity() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 3, [2, 2, 2])
        exact_intent = session.scalar(select(Intent).where(Intent.user_id == users[2].id))
        assert exact_intent is not None
        exact_intent.max_people = 2
        session.commit()
        plan = regenerate_group(session, group.id, "ekb", [item])[0]
        offers = {offer.user_id: offer for offer in session.scalars(select(Offer))}
        for user in users[:2]:
            product.accept_offer(offers[user.id].id, OfferAction(), session, SimpleNamespace(id=user.id))
        assert plan.status == "CONFIRMED_OPEN"
        assert product.offer_out(session, offers[users[2].id]).can_waitlist
        product.accept_offer(offers[users[2].id].id, OfferAction(), session, SimpleNamespace(id=users[2].id))
        assert offers[users[2].id].status == "WAITLISTED"
        product.cancel_accepted_offer(offers[users[0].id].id, session, SimpleNamespace(id=users[0].id))
        assert offers[users[2].id].status == "ACCEPTED"
        assert (plan.status, plan.required_max_people) == ("CONFIRMED", 2)


def test_place_chooses_slot_with_more_feasible_people() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 5, [2] * 5)
        day = datetime.now(UTC).date() + timedelta(days=1)
        start = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=18)
        for index, user in enumerate(users):
            intent = session.scalar(select(Intent).where(Intent.user_id == user.id))
            assert intent is not None
            intent.available_from = start if index == 0 else start + timedelta(hours=2)
            intent.available_to = start + timedelta(hours=4)
        session.commit()
        place = replace(item, item_type="PLACE", starts_at=start, ends_at=start + timedelta(hours=4), source_url="https://kudago.com/place/example/")
        plans = regenerate_group(session, group.id, "ekb", [place])
        assert len(plans) == 1
        assert plans[0].starts_at.replace(tzinfo=UTC) == start + timedelta(hours=2)
        assert len(list(session.scalars(select(Offer)))) == 5


def test_saved_places_are_private_city_scoped_and_support_default_rename_delete() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(id="place-owner", max_user_id="place-owner", display_name="Owner")
        stranger = User(id="place-stranger", max_user_id="place-stranger", display_name="Stranger")
        group = Group(id="place-group", name="Город", default_city_slug="ekb", created_by=owner.id)
        session.add_all([owner, stranger, group, GroupMember(group_id=group.id, user_id=owner.id)])
        session.commit()
        with pytest.raises(HTTPException) as wrong_city:
            product.create_location(LocationIn(label="Дом", city_slug="msk", latitude=55.7, longitude=37.6), session, owner)
        assert wrong_city.value.status_code == 422
        first = product.create_location(LocationIn(label="Дом", city_slug="ekb", latitude=56.8, longitude=60.6, address_text="Улица 1"), session, owner)
        second = product.create_location(LocationIn(label="Работа", city_slug="ekb", latitude=56.9, longitude=60.7), session, owner)
        assert first.is_default and not second.is_default and first.address_text == "Улица 1"
        with pytest.raises(HTTPException) as private:
            product.rename_location(first.id, LocationRenameIn(label="Чужое"), session, stranger)
        assert private.value.status_code == 404
        renamed = product.rename_location(second.id, LocationRenameIn(label="Офис"), session, owner)
        assert renamed.label == "Офис"
        assert product.default_location(second.id, session, owner).is_default
        assert [place.is_default for place in product.list_locations(session, owner)] == [True, False]
        session.add(Intent(user_id=owner.id, group_id=group.id, type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="games", origin_location_id=second.id, radius_km=5, min_people=2))
        session.commit()
        with pytest.raises(HTTPException) as in_use:
            product.delete_location(second.id, session, owner)
        assert in_use.value.status_code == 409
        intent = session.scalar(select(Intent).where(Intent.origin_location_id == second.id))
        assert intent is not None
        intent.status = "CANCELLED"
        session.commit()
        assert product.delete_location(second.id, session, owner) == {"status": "deleted"}
        assert session.get(Location, second.id) is None
        assert product.list_locations(session, owner)[0].is_default


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


def test_exact_group_size_accepts_two_five_and_arbitrary_n() -> None:
    current = datetime.now(UTC)
    for size in (2, 5, 9):
        payload = SignalBatchIn(
            group_ids=["group"],
            available_from=current + timedelta(hours=1),
            available_to=current + timedelta(hours=4),
            min_people=size,
            max_people=size,
        )
        assert (payload.min_people, payload.max_people) == (size, size)
    with pytest.raises(ValidationError):
        SignalBatchIn(group_ids=["group"], available_from=current + timedelta(hours=1), available_to=current + timedelta(hours=4), min_people=1, max_people=1)
    with pytest.raises(ValidationError):
        SignalBatchIn(group_ids=["group"], available_from=current + timedelta(hours=1), available_to=current + timedelta(hours=4), min_people=13, max_people=13)


def test_company_city_rejects_unsupported_provider_city(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(id="city-owner", max_user_id="city-owner", display_name="Owner")
        group = Group(id="city-group", name="Friends", default_city_slug="ekb", timezone_name="Asia/Yekaterinburg", created_by=owner.id)
        session.add_all([owner, group, GroupMember(group_id=group.id, user_id=owner.id, role="OWNER")])
        session.commit()
        monkeypatch.setattr(product, "supported_cities", lambda: {"ekb": {"slug": "ekb", "name": "Екатеринбург", "timezone": "Asia/Yekaterinburg"}})
        with pytest.raises(HTTPException) as unsupported:
            product.update_group_city(group.id, GroupCityUpdateIn(city_slug="moon"), session, owner)
        assert unsupported.value.status_code == 422
        assert group.default_city_slug == "ekb"


def test_company_city_change_cancels_mutable_state_and_preserves_confirmed_core(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        current = datetime.now(UTC)
        owner = User(id="city-owner", max_user_id="city-owner", display_name="Owner")
        friend = User(id="city-friend", max_user_id="city-friend", display_name="Friend")
        group = Group(id="city-group", name="Friends", default_city_slug="ekb", timezone_name="Asia/Yekaterinburg", created_by=owner.id)
        session.add_all([owner, friend, group])
        session.flush()
        session.add_all([
            GroupMember(group_id=group.id, user_id=owner.id, role="OWNER"),
            GroupMember(group_id=group.id, user_id=friend.id),
            Intent(user_id=owner.id, group_id=group.id, type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="games", min_people=2),
            Intent(user_id=friend.id, group_id=group.id, type="RECURRING", status="ACTIVE", city_slug="ekb", activity_category="games", min_people=2),
        ])
        collecting = CandidatePlan(group_id=group.id, city_slug="ekb", starts_at=current + timedelta(hours=2), ends_at=current + timedelta(hours=4), required_min_people=2, required_max_people=2, status="COLLECTING", expires_at=current + timedelta(hours=1))
        confirmed = CandidatePlan(group_id=group.id, city_slug="ekb", starts_at=current + timedelta(days=1), ends_at=current + timedelta(days=1, hours=2), required_min_people=2, required_max_people=2, status="CONFIRMED_OPEN", expires_at=current + timedelta(hours=6))
        session.add_all([collecting, confirmed])
        session.flush()
        collecting_pending = Offer(candidate_plan_id=collecting.id, user_id=owner.id, status="PENDING", expires_at=collecting.expires_at)
        collecting_accepted = Offer(candidate_plan_id=collecting.id, user_id=friend.id, status="ACCEPTED", expires_at=collecting.expires_at)
        confirmed_accepted = Offer(candidate_plan_id=confirmed.id, user_id=owner.id, status="ACCEPTED", expires_at=confirmed.expires_at)
        confirmed_pending = Offer(candidate_plan_id=confirmed.id, user_id=friend.id, status="PENDING", expires_at=confirmed.expires_at)
        session.add_all([collecting_pending, collecting_accepted, confirmed_accepted, confirmed_pending])
        session.flush()
        stale_notification = OutboxNotification(kind="OFFER", user_id=owner.id, payload={"offer_id": collecting_pending.id}, status="PENDING")
        session.add(stale_notification)
        session.commit()
        monkeypatch.setattr(product, "supported_cities", lambda: {"msk": {"slug": "msk", "name": "Москва", "timezone": "Europe/Moscow"}})

        result = product.update_group_city(group.id, GroupCityUpdateIn(city_slug="msk"), session, owner)

        intents = list(session.scalars(select(Intent).order_by(Intent.type)))
        assert {intent.type: intent.status for intent in intents} == {"ONE_TIME": "CANCELLED", "RECURRING": "PAUSED"}
        assert collecting.status == "CANCELLED"
        assert (collecting_pending.status, collecting_accepted.status) == ("INVALIDATED", "INVALIDATED")
        assert confirmed.status == "CONFIRMED_OPEN"
        assert (confirmed_accepted.status, confirmed_pending.status) == ("ACCEPTED", "INVALIDATED")
        assert stale_notification.status == "CANCELLED"
        assert (group.default_city_slug, group.timezone_name) == ("msk", "Europe/Moscow")
        assert (result.cancelled_signals, result.paused_autosignals, result.cancelled_plans, result.invalidated_offers) == (1, 1, 1, 3)


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


def test_signal_batch_rolls_back_failed_recompute_and_refresh_repairs_idempotently(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, group, item = seed(session, 2, [2, 2])
        current = datetime.now(UTC)
        payload = SignalBatchIn(group_ids=[group.id], available_from=current, available_to=current + timedelta(hours=6), activity_categories=["games"], min_people=2)
        def fetch_without_transaction(_query: object) -> ProviderResult:
            assert not session.in_transaction()
            return ProviderResult([item], False, current)
        monkeypatch.setattr(product, "fetch_items", fetch_without_transaction)
        real_regenerate = product.regenerate_group
        def fail_recompute(*_args: object, **_kwargs: object) -> list[CandidatePlan]:
            raise RuntimeError("recompute failed")
        monkeypatch.setattr(product, "regenerate_group", fail_recompute)
        with pytest.raises(RuntimeError):
            product.create_signal_batch(payload, session, users[0])
        session.rollback()
        assert len(list(session.scalars(select(Intent)))) == 2
        assert list(session.scalars(select(CandidatePlan))) == []
        monkeypatch.setattr(product, "regenerate_group", real_regenerate)
        created = product.create_signal_batch(payload, session, users[0])
        assert len(created.intents) == 1
        assert len(list(session.scalars(select(CandidatePlan)))) == 1
        product.refresh_signal_batch(created.signal_batch_id, session, users[0])
        assert len(list(session.scalars(select(CandidatePlan)))) == 1


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
