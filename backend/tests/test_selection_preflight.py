"""The real create -> choose path must not be blocked by obsolete commitments."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes import dvizh as routes
from app.api.schemas import SignalBatchIn
from app.core.domain_errors import DomainError, domain_error_response
from app.db.models import (
    Base,
    CandidatePlan,
    DvizhCandidate,
    DvizhConfirmation,
    DvizhReaction,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    Offer,
    OutboxNotification,
    User,
)
from app.db.session import get_session
from app.modules.auth.service import current_user
from app.modules.leisure.provider import NormalizedLeisureItem, ProviderResult


def setup(session: Session) -> tuple[User, Group, NormalizedLeisureItem, SignalBatchIn]:
    user = User(max_user_id="selection-user", display_name="Selection user")
    session.add(user)
    session.flush()
    group = Group(name="Friends", default_city_slug="msk", created_by=user.id)
    session.add(group)
    session.flush()
    session.add(GroupMember(group_id=group.id, user_id=user.id))
    starts_at = datetime.now(UTC) + timedelta(hours=2)
    item = NormalizedLeisureItem(
        provider="KUDAGO",
        provider_id="12345",
        item_type="EVENT",
        city_slug="msk",
        title="Квест",
        category="quest",
        categories=("quest",),
        classification_confidence="HIGH",
        venue_name="Лабиринт",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        latitude=None,
        longitude=None,
        price_text="500 ₽",
        price_min=500,
        price_kind="EXACT",
        source_url="https://kudago.com/12345",
        image_url=None,
        source_fetched_at=datetime.now(UTC),
    )
    payload = SignalBatchIn(
        group_ids=[group.id],
        activity_categories=["quest"],
        available_from=starts_at - timedelta(minutes=30),
        available_to=starts_at + timedelta(hours=2),
        min_people=2,
    )
    session.commit()
    return user, group, item, payload


def add_legacy_offer(
    session: Session, user: User, group: Group, item: NormalizedLeisureItem, status: str
) -> None:
    plan = CandidatePlan(
        group_id=group.id,
        city_slug="msk",
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        required_min_people=2,
        required_max_people=3,
        status=status,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    session.add(plan)
    session.flush()
    session.add(
        Offer(
            candidate_plan_id=plan.id,
            user_id=user.id,
            status="ACCEPTED",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    session.commit()


@pytest.mark.parametrize("legacy_status", [None, "EXPIRED", "CANCELLED"])
def test_clean_or_obsolete_legacy_state_allows_create_then_would_go(
    monkeypatch: pytest.MonkeyPatch,
    legacy_status: str | None,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user, group, item, payload = setup(session)
        if legacy_status:
            add_legacy_offer(session, user, group, item, legacy_status)
        monkeypatch.setattr(
            routes,
            "fetch_items",
            lambda _query: ProviderResult([item], cached=False, fetched_at=datetime.now(UTC)),
        )
        dvizh = routes.create_signal(payload, session, user, "selection-happy")["dvizhi"][0]
        candidate = dvizh["candidates"][0]
        selected = routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, user
        )
        assert selected["candidates"][0]["my_reaction"] == "WOULD_GO"
        assert session.scalar(select(DvizhReaction.value)) == "WOULD_GO"
    engine.dispose()


def gathered(session: Session, user: User, group: Group, item: NormalizedLeisureItem) -> None:
    intent = Intent(
        user_id=user.id,
        group_id=group.id,
        type="ONE_TIME",
        status="FULFILLED",
        city_slug="msk",
        activity_category="quest",
        min_people=2,
    )
    session.add(intent)
    session.flush()
    dvizh = DvizhSession(
        signal_id=intent.id,
        group_id=group.id,
        initiator_id=user.id,
        status="GATHERED",
        activity_ids=["quest"],
        min_people=2,
        max_people=3,
        expires_at=item.ends_at + timedelta(hours=1),
    )
    session.add(dvizh)
    session.flush()
    candidate = DvizhCandidate(
        session_id=dvizh.id,
        position=0,
        provider="KUDAGO",
        provider_item_id="confirmed",
        item_type="EVENT",
        title=item.title,
        activity_ids=["quest"],
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        compatibility="EXACT",
        seed=True,
        expires_at=item.starts_at - timedelta(minutes=10),
    )
    session.add(candidate)
    session.flush()
    dvizh.active_candidate_id = candidate.id
    session.add(DvizhConfirmation(candidate_id=candidate.id, user_id=user.id, status="CONFIRMED"))
    session.commit()


def test_overlapping_gathered_blocks_before_provider_and_creates_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user, group, item, payload = setup(session)
        gathered(session, user, group, item)
        user_id = user.id
        intent_count = len(list(session.scalars(select(Intent))))
        dvizh_count = len(list(session.scalars(select(DvizhSession))))
        candidate_count = len(list(session.scalars(select(DvizhCandidate))))
        notification_count = len(list(session.scalars(select(OutboxNotification))))
    provider_calls = 0

    def provider(_query: object) -> ProviderResult:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("Conflict must be rejected before provider I/O")

    monkeypatch.setattr(routes, "fetch_items", provider)
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error_response)
    app.include_router(routes.router)

    def db_session():
        with Session(engine) as session:
            yield session

    def actor():
        with Session(engine) as session:
            return session.get(User, user_id)

    app.dependency_overrides[get_session] = db_session
    app.dependency_overrides[current_user] = actor
    with TestClient(app) as client:
        response = client.post("/signals", json=payload.model_dump(mode="json"))
    assert response.status_code == 409
    assert response.json() == {
        "code": "SCHEDULE_CONFLICT",
        "detail": "У тебя уже есть движ на это время.",
    }
    assert provider_calls == 0
    with Session(engine) as session:
        assert len(list(session.scalars(select(Intent)))) == intent_count
        assert len(list(session.scalars(select(DvizhSession)))) == dvizh_count
        assert len(list(session.scalars(select(DvizhCandidate)))) == candidate_count
        assert session.scalar(select(DvizhReaction.id)) is None
        assert len(list(session.scalars(select(OutboxNotification)))) == notification_count
    engine.dispose()


def test_nonoverlapping_gathered_allows_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user, group, item, payload = setup(session)
        gathered(session, user, group, item)
        later = replace(
            item,
            provider_id="later",
            starts_at=item.ends_at + timedelta(hours=1),
            ends_at=item.ends_at + timedelta(hours=2),
        )
        later_payload = payload.model_copy(
            update={
                "available_from": later.starts_at - timedelta(minutes=30),
                "available_to": later.ends_at + timedelta(minutes=30),
            }
        )
        monkeypatch.setattr(
            routes,
            "fetch_items",
            lambda _query: ProviderResult([later], cached=False, fetched_at=datetime.now(UTC)),
        )
        result = routes.create_signal(later_payload, session, user, "later-signal")
        assert result["dvizhi"][0]["status"] == "CHOOSING_CANDIDATES"
    engine.dispose()


def test_active_legacy_confirmed_plan_still_blocks_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user, group, item, payload = setup(session)
        add_legacy_offer(session, user, group, item, "CONFIRMED")
        monkeypatch.setattr(
            routes, "fetch_items", lambda _query: pytest.fail("Provider must not be called")
        )
        with pytest.raises(DomainError) as error:
            routes.create_signal(payload, session, user, "legacy-active")
        assert error.value.status_code == 409
        assert error.value.code == "SCHEDULE_CONFLICT"
        assert len(list(session.scalars(select(DvizhSession)))) == 0
    engine.dispose()
