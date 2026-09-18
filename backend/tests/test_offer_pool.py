from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import Session

from app.api.routes.product import list_offers, offer_out
from app.db.models import (
    Base,
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
from app.modules.leisure.provider import NormalizedLeisureItem
from app.modules.matching.service import regenerate_group


def test_all_cross_group_pending_offers_are_returned_with_group_context() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    assert "leisure_items" not in inspect(engine).get_table_names()
    now = datetime.now(UTC)

    with Session(engine) as session:
        user = User(id="user", max_user_id="user", display_name="Антон")
        session.add(user)
        for index in range(5):
            group = Group(
                id=f"group-{index}", name=f"Компания {index}", default_city_slug="ekb",
                created_by=user.id, invite_token=f"invite-{index}",
            )
            location = Location(
                id=f"location-{index}", user_id=user.id, label="Дом", latitude=56.8,
                longitude=60.6, city_slug="ekb", kind="SAVED", is_ephemeral=False,
            )
            intent = Intent(
                id=f"intent-{index}", user_id=user.id, group_id=group.id, type="ONE_TIME",
                status="ACTIVE", city_slug="ekb", activity_category="other",
                available_from=now, available_to=now + timedelta(hours=4), budget_max=500,
                origin_location_id=location.id, radius_km=10, min_people=1, max_people=6,
            )
            plan = CandidatePlan(
                id=f"plan-{index}", group_id=group.id, city_slug="ekb", starts_at=now,
                ends_at=now + timedelta(hours=2), estimated_price_min=400, required_min_people=1,
                required_max_people=6, status="COLLECTING", expires_at=now + timedelta(hours=1),
            )
            session.add_all([group, location, intent, plan, GroupMember(group_id=group.id, user_id=user.id)])
            session.add(CandidatePlanSourceSnapshot(
                candidate_plan_id=plan.id, provider="KUDAGO", provider_item_id=str(index),
                provider_item_type="EVENT", title=f"Вариант {index}", category="other",
                venue_name=None, starts_at=plan.starts_at, ends_at=plan.ends_at, latitude=56.8,
                longitude=60.6, price_text=None if index == 4 else "400 ₽", parsed_price=400,
                source_url=None, image_url=None, source_fetched_at=now, is_demo=False,
            ))
            session.add(CandidatePlanMember(
                candidate_plan_id=plan.id, user_id=user.id, intent_id=intent.id,
                compatibility="NEAR" if index == 4 else "EXACT", distance_km=1.2,
                budget_delta=50 if index == 4 else None, deviations_json=None,
            ))
            session.add(Offer(
                candidate_plan_id=plan.id, user_id=user.id, status="PENDING", is_near=index == 4,
                expires_at=now + timedelta(hours=1),
            ))
        session.commit()

        queries: list[str] = []
        def count_query(_connection: object, _cursor: object, statement: str, _parameters: object, _context: object, _executemany: bool) -> None:
            queries.append(statement)
        event.listen(engine, "before_cursor_execute", count_query)
        try:
            offers = list_offers(session, user)
        finally:
            event.remove(engine, "before_cursor_execute", count_query)
        expected = {offer.id: offer_out(session, offer) for offer in session.scalars(select(Offer))}

    assert len(offers) == 5
    assert len(queries) <= 15
    assert {offer.id: offer for offer in offers} == expected
    assert {offer.group_name for offer in offers} == {f"Компания {index}" for index in range(5)}
    assert {offer.is_near for offer in offers} == {False, True}


def test_creating_candidate_plan_persists_one_source_snapshot_only() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        user = User(id="user", max_user_id="user", display_name="Антон")
        friend = User(id="friend", max_user_id="friend", display_name="Друг")
        group = Group(id="group", name="Друзья", default_city_slug="ekb", created_by=user.id, invite_token="token")
        location = Location(id="location", user_id=user.id, label="Дом", latitude=56.8, longitude=60.6, city_slug="ekb", kind="SAVED", is_ephemeral=False)
        intent = Intent(id="intent", user_id=user.id, group_id=group.id, type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="other", available_from=now, available_to=now + timedelta(hours=4), budget_max=500, origin_location_id=location.id, radius_km=10, min_people=2, max_people=None)
        friend_intent = Intent(id="friend-intent", user_id=friend.id, group_id=group.id, type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="other", available_from=now, available_to=now + timedelta(hours=4), budget_max=None, origin_location_id=None, radius_km=None, min_people=2, max_people=None)
        session.add_all([user, friend, group, location, intent, friend_intent, GroupMember(group_id=group.id, user_id=user.id), GroupMember(group_id=group.id, user_id=friend.id)])
        session.commit()
        provider_item = NormalizedLeisureItem(provider="KUDAGO", provider_id="one", item_type="EVENT", city_slug="ekb", title="Квиз", category="other", venue_name=None, starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=3), latitude=56.8, longitude=60.6, price_text="400 ₽", price_min=400, source_url=None, image_url=None, source_fetched_at=now)

        plans = regenerate_group(session, group.id, "ekb", [provider_item])

        assert len(plans) == 1
        assert session.query(CandidatePlanSourceSnapshot).count() == 1
        assert session.query(CandidatePlan).count() == 1
        assert session.query(Offer).count() == 2


def test_unverified_item_does_not_create_candidate_plan_or_snapshot() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        user = User(id="user", max_user_id="user", display_name="Антон")
        group = Group(id="group", name="Друзья", default_city_slug="ekb", created_by=user.id, invite_token="token")
        intent = Intent(id="intent", user_id=user.id, group_id=group.id, type="ONE_TIME", status="ACTIVE", city_slug="ekb", activity_category="other", available_from=now, available_to=now + timedelta(hours=4), budget_max=500, origin_location_id=None, radius_km=None, min_people=1, max_people=2)
        session.add_all([user, group, intent])
        session.commit()
        provider_item = NormalizedLeisureItem(provider="KUDAGO", provider_id="unpriced", item_type="EVENT", city_slug="ekb", title="Без цены", category="other", venue_name=None, starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=3), latitude=None, longitude=None, price_text=None, price_min=None, source_url=None, image_url=None, source_fetched_at=now)

        assert regenerate_group(session, group.id, "ekb", [provider_item]) == []
        assert session.query(CandidatePlan).count() == 0
        assert session.query(CandidatePlanSourceSnapshot).count() == 0
        assert session.query(Offer).count() == 0
