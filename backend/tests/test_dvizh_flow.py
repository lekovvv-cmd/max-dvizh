"""New product flow with real persistence, privacy and idempotent state changes."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes import dvizh as routes
from app.api.schemas import AutoSignalIn, SignalBatchIn
from app.db.models import (
    Base,
    DvizhConfirmation,
    DvizhReaction,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    OutboxNotification,
    User,
)
from app.modules.leisure import provider as leisure_provider
from app.modules.leisure.provider import NormalizedLeisureItem, ProviderQuery, ProviderResult
from app.modules.leisure.taxonomy import BY_ID, classify, expand, valid_selection
from app.modules.matching.dvizh import _daily_hours_fit, eligible_reaction_count, recompute


def fixture(
    session: Session, groups: int = 1
) -> tuple[list[User], list[Group], NormalizedLeisureItem, SignalBatchIn]:
    users = [User(max_user_id=str(index), display_name=f"Person {index}") for index in range(3)]
    session.add_all(users)
    session.flush()
    companies = [
        Group(
            name=f"Company {index}",
            default_city_slug="msk",
            timezone_name="Europe/Moscow",
            created_by=users[0].id,
        )
        for index in range(groups)
    ]
    session.add_all(companies)
    session.flush()
    for group in companies:
        session.add_all(GroupMember(group_id=group.id, user_id=user.id) for user in users)
    start = datetime.now(UTC) + timedelta(hours=2)
    item = NormalizedLeisureItem(
        provider="KUDAGO",
        provider_id="quest-1",
        item_type="EVENT",
        city_slug="msk",
        title="Квест «Лабиринт»",
        category="quest",
        categories=("quest",),
        classification_confidence="HIGH",
        venue_name="Лабиринт",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        latitude=None,
        longitude=None,
        price_text="500 ₽",
        price_min=500,
        price_kind="EXACT",
        source_url="https://kudago.com/quest-1",
        image_url=None,
        source_fetched_at=datetime.now(UTC),
    )
    payload = SignalBatchIn(
        group_ids=[group.id for group in companies],
        activity_categories=["quest"],
        available_from=start - timedelta(hours=1),
        available_to=start + timedelta(hours=2),
        budget_max=1000,
        min_people=3,
    )
    session.commit()
    return users, companies, item, payload


def create(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    item: NormalizedLeisureItem,
    payload: SignalBatchIn,
    user: User,
) -> dict[str, object]:
    monkeypatch.setattr(
        routes,
        "fetch_items",
        lambda query: ProviderResult([item], cached=False, fetched_at=datetime.now(UTC)),
    )
    return routes.create_signal(payload, session, user, "request-1")


def test_taxonomy_and_strict_classifier() -> None:
    assert classify({"categories": ["questroom"]}, "PLACE")["quest"] == "HIGH"
    assert classify({"tags": ["настольные игры"]}, "PLACE")["board_games"] == "HIGH"
    assert classify({"title": "Батутный центр"}, "PLACE")["trampoline"] == "HIGH"
    assert classify({"tags": ["бани"]}, "PLACE")["sauna"] == "HIGH"
    assert classify({"title": "Новый боулинг"}, "PLACE")["bowling"] == "HIGH"
    assert classify({"description": "есть компьютерный клуб"}, "PLACE")["pc_club"] == "LOW"
    assert set(BY_ID["bowling"].directions) == {"games", "active"}
    assert "pc_club" not in expand(["games/*"])
    assert "thermal" not in expand(["relax/*"])
    assert "pc_club" not in expand(["anticafe"])
    assert not valid_selection(["pc_club", "bowling"])
    assert not valid_selection(["games"])


def test_provider_gmt_offset_is_used_for_place_hours() -> None:
    start = datetime(2026, 9, 25, 13, tzinfo=UTC)
    assert _daily_hours_fit("ежедневно 10:00–20:00", start, start + timedelta(hours=2), "GMT+03:00")
    assert not _daily_hours_fit(
        "ежедневно 10:00–17:00", start, start + timedelta(hours=2), "GMT+03:00"
    )


def test_provider_weekly_and_overnight_hours_are_checked_without_guessing() -> None:
    # Actual KudaGo timetable shapes for a bowling club and trampoline centre.
    bowling = "пн–чт 11:00–23:00, пт 11:00–6:00, сб 10:00–6:00, вс 10:00–23:00"
    trampoline = "пн–пт 11:00–22:00, сб, вс 10:00–22:00"
    friday = datetime(2026, 9, 25, 21, tzinfo=UTC)  # Saturday 00:00 in St Petersburg
    assert _daily_hours_fit(bowling, friday, friday + timedelta(hours=2), "Europe/Moscow")
    assert not _daily_hours_fit(
        bowling, friday + timedelta(hours=6), friday + timedelta(hours=8), "Europe/Moscow"
    )
    saturday = datetime(2026, 9, 26, 8, tzinfo=UTC)
    assert _daily_hours_fit(trampoline, saturday, saturday + timedelta(hours=2), "Europe/Moscow")
    assert not _daily_hours_fit(
        trampoline + ", часы уточняйте", saturday, saturday + timedelta(hours=2), "Europe/Moscow"
    )


def test_full_flow_no_early_notifications_and_private_reactions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, groups, item, payload = fixture(session)
        # A different active Signal is a positive hint, never an audience exclusion.
        session.add(
            Intent(
                user_id=users[1].id,
                group_id=groups[0].id,
                type="ONE_TIME",
                status="ACTIVE",
                city_slug="msk",
                activity_category="bowling",
                activity_categories=["bowling"],
                available_from=payload.available_from,
                available_to=payload.available_to,
                min_people=2,
            )
        )
        session.commit()
        result = create(monkeypatch, session, item, payload, users[0])

        def unexpected_provider_call(_query: ProviderQuery) -> ProviderResult:
            raise AssertionError("An idempotent retry must not call KudaGo")

        monkeypatch.setattr(routes, "fetch_items", unexpected_provider_call)
        repeated = routes.create_signal(payload, session, users[0], "request-1")
        assert repeated["signal_batch_id"] == result["signal_batch_id"]
        dvizh = result["dvizhi"][0]
        assert dvizh["status"] == "CHOOSING_CANDIDATES"
        assert routes.list_dvizhi(session, users[1]) == []
        candidate = dvizh["candidates"][0]
        assert list(session.scalars(select(OutboxNotification))) == []
        routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, users[0]
        )
        assert list(session.scalars(select(OutboxNotification))) == []
        launched = routes.launch(dvizh["id"], session, users[0])
        assert launched["status"] == "COLLECTING_REACTIONS"
        assert launched["confirmed_count"] == 0
        review = list(
            session.scalars(
                select(OutboxNotification).where(OutboxNotification.kind == "DVIZH_REVIEW_REQUIRED")
            )
        )
        assert {notification.user_id for notification in review} == {users[1].id, users[2].id}
        routes.launch(dvizh["id"], session, users[0])
        assert (
            len(
                list(
                    session.scalars(
                        select(OutboxNotification).where(
                            OutboxNotification.kind == "DVIZH_REVIEW_REQUIRED"
                        )
                    )
                )
            )
            == 2
        )
        friend = routes.get_dvizh_detail(dvizh["id"], session, users[1])
        assert friend["candidates"][0]["my_reaction"] is None
        assert friend["participants"] == []
        routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, users[1]
        )
        matched = routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, users[2]
        )
        assert matched["status"] == "AWAITING_CONFIRMATION"
        assert matched["reaction_count"] == 3
        assert matched["confirmed_count"] == 0
        assert matched["participants"] == []
        assert (
            len(
                list(
                    session.scalars(
                        select(OutboxNotification).where(
                            OutboxNotification.kind == "DVIZH_MATCH_FOUND"
                        )
                    )
                )
            )
            == 3
        )
        with pytest.raises(HTTPException) as stale:
            routes.confirm(
                dvizh["id"], routes.ConfirmationIn(candidate_id="old-candidate"), session, users[0]
            )
        assert stale.value.status_code == 409
        assert list(session.scalars(select(DvizhConfirmation))) == []
        routes.confirm(
            dvizh["id"], routes.ConfirmationIn(candidate_id=candidate["id"]), session, users[0]
        )
        routes.confirm(
            dvizh["id"], routes.ConfirmationIn(candidate_id=candidate["id"]), session, users[1]
        )
        gathered = routes.confirm(
            dvizh["id"], routes.ConfirmationIn(candidate_id=candidate["id"]), session, users[2]
        )
        assert gathered["status"] == "GATHERED"
        assert gathered["confirmed_count"] == 3
        assert len(gathered["participants"]) == 3
        stored_signal = session.scalar(
            select(Intent).where(Intent.signal_batch_id == result["signal_batch_id"])
        )
        assert stored_signal is not None and stored_signal.status == "FULFILLED"
        routes.confirm(
            dvizh["id"], routes.ConfirmationIn(candidate_id=candidate["id"]), session, users[2]
        )
        assert len(list(session.scalars(select(DvizhConfirmation)))) == 3
        assert len(list(session.scalars(select(DvizhReaction)))) == 3
        assert (
            len(
                list(
                    session.scalars(
                        select(OutboxNotification).where(
                            OutboxNotification.kind == "DVIZH_GATHERED"
                        )
                    )
                )
            )
            == 3
        )


def test_launch_rechecks_company_size_after_member_leaves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, groups, item, payload = fixture(session)
        dvizh = create(monkeypatch, session, item, payload, users[0])["dvizhi"][0]
        candidate = dvizh["candidates"][0]
        routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, users[0]
        )
        departed = session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == groups[0].id, GroupMember.user_id == users[2].id
            )
        )
        assert departed is not None
        session.delete(departed)
        session.commit()

        with pytest.raises(HTTPException) as blocked:
            routes.launch(dvizh["id"], session, users[0])
        assert blocked.value.status_code == 409
        assert session.get(DvizhSession, dvizh["id"]).status == "CHOOSING_CANDIDATES"
        assert list(session.scalars(select(OutboxNotification))) == []

        session.add(GroupMember(group_id=groups[0].id, user_id=users[2].id))
        session.commit()
        assert routes.launch(dvizh["id"], session, users[0])["status"] == "COLLECTING_REACTIONS"


def test_cancelled_provider_item_is_not_launched_or_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, _, item, payload = fixture(session)
        dvizh = create(monkeypatch, session, item, payload, users[0])["dvizhi"][0]
        candidate = dvizh["candidates"][0]
        routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, users[0]
        )
        monkeypatch.setattr(routes, "_source_available", lambda candidate: False)
        with pytest.raises(HTTPException) as cancelled:
            routes.launch(dvizh["id"], session, users[0])
        assert cancelled.value.status_code == 409
        assert session.get(DvizhSession, dvizh["id"]).status == "NO_SOURCE"
        assert list(session.scalars(select(OutboxNotification))) == []
        assert routes.list_dvizhi(session, users[1]) == []
        with pytest.raises(HTTPException) as hidden:
            routes.get_dvizh_detail(dvizh["id"], session, users[1])
        assert hidden.value.status_code == 404
        routes.cancel_signal(dvizh["signal_batch_id"], session, users[0])
        assert session.get(DvizhSession, dvizh["id"]).status == "CANCELLED"
        assert routes.list_dvizhi(session, users[1]) == []

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, _, item, payload = fixture(session)
        dvizh = create(monkeypatch, session, item, payload, users[0])["dvizhi"][0]
        candidate = dvizh["candidates"][0]
        monkeypatch.setattr(routes, "_source_available", lambda candidate: True)
        routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, users[0]
        )
        routes.launch(dvizh["id"], session, users[0])
        for user in users[1:]:
            routes.react(
                dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, user
            )
        assert session.get(DvizhSession, dvizh["id"]).status == "AWAITING_CONFIRMATION"
        monkeypatch.setattr(routes, "_source_available", lambda candidate: False)
        with pytest.raises(HTTPException) as cancelled:
            routes.confirm(
                dvizh["id"], routes.ConfirmationIn(candidate_id=candidate["id"]), session, users[0]
            )
        assert cancelled.value.status_code == 409
        assert session.get(DvizhSession, dvizh["id"]).status == "NO_MATCH"
        assert list(session.scalars(select(DvizhConfirmation))) == []
        match_notices = list(
            session.scalars(
                select(OutboxNotification).where(OutboxNotification.kind == "DVIZH_MATCH_FOUND")
            )
        )
        assert len(match_notices) == 3
        assert all(notice.status == "CANCELLED" for notice in match_notices)


def test_source_cancelled_after_gathering_notifies_confirmed_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, _, item, payload = fixture(session)
        dvizh = create(monkeypatch, session, item, payload, users[0])["dvizhi"][0]
        candidate = dvizh["candidates"][0]
        monkeypatch.setattr(routes, "_source_available", lambda candidate: True)
        routes.react(
            dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, users[0]
        )
        routes.launch(dvizh["id"], session, users[0])
        for user in users[1:]:
            routes.react(
                dvizh["id"], candidate["id"], routes.ReactionIn(value="WOULD_GO"), session, user
            )
        for user in users:
            routes.confirm(
                dvizh["id"], routes.ConfirmationIn(candidate_id=candidate["id"]), session, user
            )
        assert session.get(DvizhSession, dvizh["id"]).status == "GATHERED"
        monkeypatch.setattr(routes, "_source_available", lambda candidate: False)
        with pytest.raises(HTTPException) as cancelled:
            routes.confirm(
                dvizh["id"], routes.ConfirmationIn(candidate_id=candidate["id"]), session, users[0]
            )
        assert cancelled.value.status_code == 409
        assert session.get(DvizhSession, dvizh["id"]).status == "CANCELLED"
        notices = list(
            session.scalars(
                select(OutboxNotification).where(
                    OutboxNotification.kind == "DVIZH_SOURCE_CANCELLED"
                )
            )
        )
        assert {notice.user_id for notice in notices} == {user.id for user in users}
        gathered = list(
            session.scalars(
                select(OutboxNotification).where(OutboxNotification.kind == "DVIZH_GATHERED")
            )
        )
        assert all(notice.status == "CANCELLED" for notice in gathered)


def test_batch_isolated_per_company_and_near_requires_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, groups, item, payload = fixture(session, groups=2)
        item = NormalizedLeisureItem(**{**item.__dict__, "price_min": 1100, "price_text": "1100 ₽"})
        result = create(monkeypatch, session, item, payload, users[0])
        dvizhi = result["dvizhi"]
        assert len(dvizhi) == 2 and dvizhi[0]["id"] != dvizhi[1]["id"]
        assert {session.get(DvizhSession, dvizh["id"]).group_id for dvizh in dvizhi} == {
            group.id for group in groups
        }
        candidate = dvizhi[0]["candidates"][0]
        assert candidate["compatibility"] == "NEAR"
        with pytest.raises(HTTPException) as denied:
            routes.react(
                dvizhi[0]["id"],
                candidate["id"],
                routes.ReactionIn(value="WOULD_GO"),
                session,
                users[0],
            )
        assert denied.value.status_code == 409
        routes.react(
            dvizhi[0]["id"],
            candidate["id"],
            routes.ReactionIn(value="WOULD_GO", confirm_near_exception=True),
            session,
            users[0],
        )
        assert routes.get_dvizh_detail(dvizhi[1]["id"], session, users[0])["chosen_count"] == 0


def test_confirmation_capacity_keeps_extra_member_on_private_waitlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, groups, item, payload = fixture(session)
        fourth = User(max_user_id="fourth", display_name="Person fourth")
        session.add(fourth)
        session.flush()
        session.add(GroupMember(group_id=groups[0].id, user_id=fourth.id))
        session.commit()
        payload.min_people = 2
        payload.max_people = 2
        result = create(monkeypatch, session, item, payload, users[0])
        dvizh_id = result["dvizhi"][0]["id"]
        candidate_id = result["dvizhi"][0]["candidates"][0]["id"]
        routes.react(dvizh_id, candidate_id, routes.ReactionIn(value="WOULD_GO"), session, users[0])
        routes.launch(dvizh_id, session, users[0])
        for user in [*users[1:], fourth]:
            routes.react(dvizh_id, candidate_id, routes.ReactionIn(value="WOULD_GO"), session, user)
        for user in users[:2]:
            routes.confirm(
                dvizh_id, routes.ConfirmationIn(candidate_id=candidate_id), session, user
            )
        assert routes.get_dvizh_detail(dvizh_id, session, users[0])["status"] == "GATHERED"
        for user in [users[2], fourth]:
            result = routes.confirm(
                dvizh_id, routes.ConfirmationIn(candidate_id=candidate_id), session, user
            )
            assert result["my_confirmation"] == "WAITLISTED"
            assert result["confirmed_count"] == 2
            assert {person["id"] for person in result["participants"]} == {
                users[0].id,
                users[1].id,
            }
        routes.confirm(dvizh_id, routes.ConfirmationIn(candidate_id=candidate_id), session, fourth)
        assert (
            len(
                list(
                    session.scalars(
                        select(DvizhConfirmation).where(DvizhConfirmation.status == "CONFIRMED")
                    )
                )
            )
            == 2
        )


def test_unverified_never_becomes_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, _, item, payload = fixture(session)
        item = NormalizedLeisureItem(**{**item.__dict__, "price_min": None, "price_text": None})
        result = create(monkeypatch, session, item, payload, users[0])
        assert result["dvizhi"][0]["status"] == "NO_SOURCE"
        assert result["dvizhi"][0]["candidates"] == []


def test_no_source_round_and_signal_expire_together(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, _, item, payload = fixture(session)
        item = NormalizedLeisureItem(**{**item.__dict__, "price_min": None, "price_text": None})
        result = create(monkeypatch, session, item, payload, users[0])
        dvizh = session.get(DvizhSession, result["dvizhi"][0]["id"])
        signal = session.scalar(select(Intent).where(Intent.signal_batch_id == "request-1"))
        assert dvizh is not None and signal is not None
        assert dvizh.status == "NO_SOURCE" and signal.status == "ACTIVE"
        dvizh.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        recompute(session, dvizh)
        assert dvizh.status == "EXPIRED"
        assert signal.status == "EXPIRED"


def test_signal_rejects_minimum_larger_than_company_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, groups, _, payload = fixture(session)
        session.delete(
            session.scalar(
                select(GroupMember).where(
                    GroupMember.group_id == groups[0].id,
                    GroupMember.user_id == users[2].id,
                )
            )
        )
        session.commit()
        monkeypatch.setattr(
            routes,
            "fetch_items",
            lambda _query: pytest.fail("Invalid group size must be rejected before KudaGo"),
        )
        with pytest.raises(HTTPException) as denied:
            routes.create_signal(payload, session, users[0], "undersized-company")
        assert denied.value.status_code == 422

        tomorrow = datetime.now(UTC) + timedelta(days=1)
        recurring = AutoSignalIn(
            group_id=groups[0].id,
            name="Пятничный движ",
            city_slug="msk",
            activity_category="quest",
            activity_categories=["quest"],
            weekdays=[tomorrow.weekday()],
            local_start="12:00",
            local_end="18:00",
            timezone="UTC",
            min_people=3,
        )
        with pytest.raises(HTTPException) as denied:
            routes.create_recurring(recurring, session, users[0])
        assert denied.value.status_code == 422


def test_manual_name_search_keeps_only_confident_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self, value):
            self.value = value

        def raise_for_status(self):
            pass

        def json(self):
            return self.value

    def get(url, **kwargs):
        if url.endswith("/search/"):
            return Response({"results": [{"id": 1}, {"id": 2}]})
        return Response(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Квест Лабиринт",
                        "site_url": "https://kudago.com/1",
                        "timetable": "ежедневно 1:00–23:30",
                        "categories": ["questroom"],
                    },
                    {
                        "id": 2,
                        "title": "Просто кафе",
                        "description": "иногда проводим квест",
                        "site_url": "https://kudago.com/2",
                        "timetable": "ежедневно 1:00–23:30",
                        "categories": [],
                    },
                ]
            }
        )

    monkeypatch.setattr(leisure_provider.httpx, "get", get)
    current = datetime.now(UTC)
    query = ProviderQuery(
        "msk", current + timedelta(days=1), current + timedelta(days=1, hours=2), ("quest",), True
    )
    found = leisure_provider.KudaGoProvider().search_place_items(query, "Лабиринт")
    assert [item.provider_id for item in found] == ["1"]


def test_decline_moves_existing_reactions_to_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, _, item, payload = fixture(session)
        backup = NormalizedLeisureItem(
            **{**item.__dict__, "provider_id": "quest-2", "title": "Квест «Выход»"}
        )
        monkeypatch.setattr(
            routes,
            "fetch_items",
            lambda query: ProviderResult(
                [item, backup], cached=False, fetched_at=datetime.now(UTC)
            ),
        )
        result = routes.create_signal(payload, session, users[0], "backup-case")
        dvizh_id = result["dvizhi"][0]["id"]
        first, second = [candidate["id"] for candidate in result["dvizhi"][0]["candidates"]]
        for candidate_id in (first, second):
            routes.react(
                dvizh_id, candidate_id, routes.ReactionIn(value="WOULD_GO"), session, users[0]
            )
        routes.launch(dvizh_id, session, users[0])
        for user in users[1:]:
            for candidate_id in (first, second):
                routes.react(
                    dvizh_id, candidate_id, routes.ReactionIn(value="WOULD_GO"), session, user
                )
        before = routes.get_dvizh_detail(dvizh_id, session, users[0])
        assert before["active_candidate_id"] == first
        routes.confirm(dvizh_id, routes.ConfirmationIn(candidate_id=first), session, users[0])
        after = routes.decline(dvizh_id, session, users[2])
        assert after["active_candidate_id"] == second
        assert after["confirmed_count"] == 0
        with pytest.raises(HTTPException) as stale:
            routes.confirm(dvizh_id, routes.ConfirmationIn(candidate_id=first), session, users[0])
        assert stale.value.status_code == 409
        previous = session.scalar(
            select(DvizhConfirmation).where(
                DvizhConfirmation.candidate_id == first, DvizhConfirmation.user_id == users[0].id
            )
        )
        assert previous and previous.status == "SUPERSEDED"


def test_departed_member_decline_does_not_cancel_remaining_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, groups, item, payload = fixture(session)
        payload.min_people = 2
        result = create(monkeypatch, session, item, payload, users[0])
        dvizh_id = result["dvizhi"][0]["id"]
        candidate_id = result["dvizhi"][0]["candidates"][0]["id"]
        routes.react(dvizh_id, candidate_id, routes.ReactionIn(value="WOULD_GO"), session, users[0])
        routes.launch(dvizh_id, session, users[0])
        for user in users[1:]:
            routes.react(dvizh_id, candidate_id, routes.ReactionIn(value="WOULD_GO"), session, user)
        routes.decline(dvizh_id, session, users[2])
        membership = session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == groups[0].id,
                GroupMember.user_id == users[2].id,
            )
        )
        assert membership is not None
        session.delete(membership)
        session.flush()
        dvizh = session.get(DvizhSession, dvizh_id)
        assert dvizh is not None
        assert eligible_reaction_count(session, candidate_id) == 2
        recompute(session, dvizh)
        assert dvizh.status == "AWAITING_CONFIRMATION"
        assert dvizh.active_candidate_id == candidate_id


def test_recurring_rule_materializes_once_into_new_private_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users, groups, _, _ = fixture(session)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        payload = AutoSignalIn(
            group_id=groups[0].id,
            name="Пятничный движ",
            city_slug="msk",
            activity_category="quest",
            activity_categories=["quest"],
            weekdays=[tomorrow.weekday()],
            local_start="12:00",
            local_end="18:00",
            timezone="UTC",
            min_people=3,
        )
        monkeypatch.setattr(
            routes,
            "fetch_items",
            lambda query: ProviderResult([], cached=False, fetched_at=datetime.now(UTC)),
        )
        rule = routes.create_recurring(payload, session, users[0])
        assert rule["status"] == "ACTIVE"
        stored = session.get(Intent, rule["id"])
        assert stored and stored.flow_version == 2
        assert routes.materialize_recurring(session, stored, users[0]) is False
        children = list(
            session.scalars(
                select(Intent).where(Intent.type == "ONE_TIME", Intent.flow_version == 2)
            )
        )
        assert len(children) == 1
        assert children[0].recurrence_json == {"parent_rule_id": rule["id"]}
        assert routes.list_dvizhi(session, users[1]) == []
        routes.cancel_recurring(rule["id"], session, users[0])
        assert stored.status == "CANCELLED"
        assert children[0].status == "CANCELLED"
