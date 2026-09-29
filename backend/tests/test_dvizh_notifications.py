"""Timed Dvizh questions stay one-shot and stop after the state changes."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes import dvizh as routes
from app.api.routes import max_webhook
from app.core.config import Settings
from app.db.models import (
    Base,
    DvizhCandidate,
    DvizhConfirmation,
    DvizhReaction,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    OutboxNotification,
    User,
)
from app.db.session import get_session
from app.modules.matching.dvizh import expire, premeet_due_time
from app.modules.matching.notifications import (
    process_gathered,
    schedule_match_reminders,
    schedule_review_reminders,
)
from app.modules.max_integration import client as max_client
from app.modules.max_integration.client import dvizh_notification_current


@pytest.mark.parametrize(
    ("hours_before", "expected_hours_before"),
    [(72, 24), (49, 24), (48, 6), (12, 6), (11, 2), (3, 2), (2, None)],
)
def test_premeet_time_buckets(hours_before: int, expected_hours_before: int | None) -> None:
    start = datetime(2026, 10, 10, 18, tzinfo=UTC)
    gathered = start - timedelta(hours=hours_before)
    expected = (
        start - timedelta(hours=expected_hours_before)
        if expected_hours_before is not None
        else gathered
    )
    assert premeet_due_time(start, gathered) == expected


def _gathered(session: Session) -> tuple[DvizhSession, DvizhCandidate, list[User]]:
    current = datetime.now(UTC)
    users = [
        User(max_user_id=f"notify-{index}", display_name=f"Person {index}") for index in range(3)
    ]
    session.add_all(users)
    session.flush()
    group = Group(name="Friends", default_city_slug="msk", created_by=users[0].id)
    session.add(group)
    session.flush()
    session.add_all(GroupMember(group_id=group.id, user_id=user.id) for user in users)
    signal = Intent(
        user_id=users[0].id,
        group_id=group.id,
        type="ONE_TIME",
        flow_version=2,
        status="FULFILLED",
        city_slug="msk",
        activity_category="quest",
        min_people=2,
    )
    session.add(signal)
    session.flush()
    dvizh = DvizhSession(
        signal_id=signal.id,
        group_id=group.id,
        initiator_id=users[0].id,
        status="GATHERED",
        activity_ids=["quest"],
        min_people=2,
        max_people=2,
        expires_at=current + timedelta(hours=4),
        premeet_due_at=current - timedelta(minutes=1),
    )
    session.add(dvizh)
    session.flush()
    candidate = DvizhCandidate(
        session_id=dvizh.id,
        position=0,
        provider="KUDAGO",
        provider_item_id="12345",
        item_type="EVENT",
        title="Quest",
        venue_name="Arcade",
        activity_ids=["quest"],
        starts_at=current + timedelta(hours=2),
        ends_at=current + timedelta(hours=3),
        compatibility="EXACT",
        seed=True,
        expires_at=current + timedelta(hours=1, minutes=50),
    )
    session.add(candidate)
    session.flush()
    dvizh.active_candidate_id = candidate.id
    session.add_all(
        DvizhConfirmation(candidate_id=candidate.id, user_id=user.id, status="CONFIRMED")
        for user in users[:2]
    )
    session.add(
        DvizhConfirmation(candidate_id=candidate.id, user_id=users[2].id, status="WAITLISTED")
    )
    session.commit()
    return dvizh, candidate, users


def _events(session: Session, kind: str) -> list[OutboxNotification]:
    return list(session.scalars(select(OutboxNotification).where(OutboxNotification.kind == kind)))


def test_premeet_question_reminder_dedupe_and_stale_after_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.matching import notifications

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dvizh, candidate, users = _gathered(session)
        monkeypatch.setattr(notifications, "source_available", lambda _candidate: True)
        process_gathered(session, datetime.now(UTC))
        process_gathered(session, datetime.now(UTC))
        questions = _events(session, "DVIZH_PREMEET_CHECK")
        assert len(questions) == 2
        assert all(dvizh_notification_current(session, event) for event in questions)
        for event in questions:
            event.status = "SENT"
            event.sent_at = datetime.now(UTC) - timedelta(minutes=31)
        session.commit()
        process_gathered(session, datetime.now(UTC))
        process_gathered(session, datetime.now(UTC))
        assert len(_events(session, "DVIZH_PREMEET_REMINDER")) == 2
        answered = routes.reconfirm(
            dvizh.id, routes.ConfirmationIn(candidate_id=candidate.id), session, users[0]
        )
        assert answered["my_reconfirmed"] is True
        assert all(
            not dvizh_notification_current(session, event)
            for event in questions + _events(session, "DVIZH_PREMEET_REMINDER")
            if event.user_id == users[0].id
        )
        process_gathered(session, datetime.now(UTC))
        assert len(_events(session, "DVIZH_PREMEET_REMINDER")) == 2
    engine.dispose()


def test_premeet_source_disappearance_notifies_confirmed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.matching import notifications

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dvizh, _, _ = _gathered(session)
        monkeypatch.setattr(notifications, "source_available", lambda _candidate: False)
        process_gathered(session, datetime.now(UTC))
        process_gathered(session, datetime.now(UTC))
        assert dvizh.status == "CANCELLED"
        assert len(_events(session, "DVIZH_SOURCE_CANCELLED")) == 2
        assert not _events(session, "DVIZH_PREMEET_CHECK")
    engine.dispose()


def test_source_cancelled_after_early_question_is_caught_near_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.matching import notifications

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dvizh, candidate, _ = _gathered(session)
        candidate.starts_at = datetime.now(UTC) + timedelta(hours=3)
        session.commit()
        monkeypatch.setattr(notifications, "source_available", lambda _candidate: True)
        process_gathered(session, datetime.now(UTC))
        assert len(_events(session, "DVIZH_PREMEET_CHECK")) == 2
        assert dvizh.source_rechecked_at is None
        candidate.starts_at = datetime.now(UTC) + timedelta(hours=1, minutes=55)
        session.commit()
        monkeypatch.setattr(notifications, "source_available", lambda _candidate: False)
        process_gathered(session, datetime.now(UTC))
        process_gathered(session, datetime.now(UTC))
        assert dvizh.status == "CANCELLED"
        assert dvizh.source_rechecked_at is not None
        assert len(_events(session, "DVIZH_SOURCE_CANCELLED")) == 2
        assert all(event.status == "CANCELLED" for event in _events(session, "DVIZH_PREMEET_CHECK"))
    engine.dispose()


def test_withdrawal_promotes_waitlist_and_invalidates_old_question() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dvizh, candidate, users = _gathered(session)
        from app.modules.matching.dvizh import enqueue

        enqueue(session, "DVIZH_PREMEET_CHECK", users[1].id, dvizh, candidate)
        session.commit()
        result = routes.withdraw(
            dvizh.id, routes.ConfirmationIn(candidate_id=candidate.id), session, users[1]
        )
        assert result["status"] == "GATHERED"
        assert result["confirmed_count"] == 2
        assert result["my_confirmation"] == "DECLINED"
        assert (
            session.scalar(
                select(DvizhConfirmation.status).where(
                    DvizhConfirmation.candidate_id == candidate.id,
                    DvizhConfirmation.user_id == users[2].id,
                )
            )
            == "CONFIRMED"
        )
        promoted = _events(session, "DVIZH_WAITLIST_AVAILABLE")
        assert len(promoted) == 1 and promoted[0].user_id == users[2].id
        assert dvizh_notification_current(session, promoted[0])
        assert not dvizh_notification_current(session, _events(session, "DVIZH_PREMEET_CHECK")[0])
    engine.dispose()


def test_review_and_match_reminders_are_one_shot() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dvizh, candidate, users = _gathered(session)
        current = datetime.now(UTC)
        dvizh.status = "CHOOSING_CANDIDATES"
        candidate.seed = False
        original = OutboxNotification(
            kind="DVIZH_INITIATOR_REVIEW",
            user_id=users[0].id,
            dedupe_key=f"DVIZH_INITIATOR_REVIEW:{dvizh.id}:review:{users[0].id}",
            payload={"dvizh_id": dvizh.id},
            status="SENT",
            sent_at=current - timedelta(minutes=31),
        )
        session.add(original)
        session.commit()
        schedule_review_reminders(session, dvizh, current)
        schedule_review_reminders(session, dvizh, current)
        session.commit()
        assert len(_events(session, "DVIZH_INITIATOR_REVIEW_REMINDER")) == 1
        dvizh.status = "AWAITING_CONFIRMATION"
        candidate.seed = True
        waiting = session.scalar(
            select(DvizhConfirmation).where(
                DvizhConfirmation.candidate_id == candidate.id,
                DvizhConfirmation.user_id == users[2].id,
            )
        )
        assert waiting is not None
        session.delete(waiting)
        session.add(DvizhReaction(candidate_id=candidate.id, user_id=users[2].id, value="WOULD_GO"))
        original = OutboxNotification(
            kind="DVIZH_MATCH_FOUND",
            user_id=users[2].id,
            dedupe_key=f"DVIZH_MATCH_FOUND:{dvizh.id}:{candidate.id}:{users[2].id}",
            payload={"dvizh_id": dvizh.id, "candidate_id": candidate.id},
            status="SENT",
            sent_at=current - timedelta(minutes=16),
        )
        session.add(original)
        session.commit()
        schedule_match_reminders(session, dvizh, current)
        schedule_match_reminders(session, dvizh, current)
        session.commit()
        reminders = _events(session, "DVIZH_MATCH_REMINDER")
        assert len(reminders) == 1
        assert dvizh_notification_current(session, reminders[0])
        session.add(
            DvizhConfirmation(candidate_id=candidate.id, user_id=users[2].id, status="DECLINED")
        )
        session.commit()
        assert not dvizh_notification_current(session, reminders[0])
    engine.dispose()


def test_expired_dvizh_notifies_initiator_once() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dvizh, _, users = _gathered(session)
        dvizh.status = "COLLECTING_REACTIONS"
        dvizh.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        expire(session, dvizh)
        expire(session, dvizh)
        session.commit()
        notices = _events(session, "DVIZH_NOT_GATHERED")
        assert dvizh.status == "EXPIRED"
        assert len(notices) == 1 and notices[0].user_id == users[0].id
        assert dvizh_notification_current(session, notices[0])
    engine.dispose()


def test_max_premeet_push_has_two_actions_details_and_exact_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        max_client, "settings", Settings(max_bot_token="test-token", max_bot_username="test_bot")
    )
    bodies: list[dict[str, object]] = []

    class Response:
        def raise_for_status(self) -> None:
            pass

    def post(*_args: object, **kwargs: object) -> Response:
        bodies.append(kwargs["json"])  # type: ignore[arg-type]
        return Response()

    monkeypatch.setattr(max_client.httpx, "post", post)
    event = OutboxNotification(
        kind="DVIZH_PREMEET_CHECK",
        user_id="user-1",
        payload={
            "dvizh_id": "session-1",
            "candidate_id": "option-1",
            "group_name": "Friends",
            "title": "Quest",
            "venue_name": "Arcade",
            "starts_at": "2026-10-10T18:00:00+00:00",
            "timezone": "Europe/Moscow",
        },
    )
    assert max_client.send_dvizh_message("123", event)
    body = bodies[0]
    assert "⚡️ Движ скоро\nArcade · 10.10 21:00\nТы всё ещё в деле?" in body["text"]
    assert all(field in body["text"] for field in ("Компания:", "Что:", "Дата и время:", "Место:"))
    buttons = body["attachments"][0]["payload"]["buttons"]  # type: ignore[index]
    assert buttons[0] == [
        {"type": "callback", "text": "Я иду", "payload": "reconfirm:session-1:option-1"},
        {"type": "callback", "text": "Не смогу", "payload": "withdraw:session-1:option-1"},
    ]
    assert buttons[1][0]["url"] == "https://max.ru/test_bot?startapp=dvizh_session-1"


def test_max_callbacks_reconfirm_and_withdraw_are_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dvizh, candidate, _ = _gathered(session)
        dvizh_id, candidate_id = dvizh.id, candidate.id
    app = FastAPI()
    app.include_router(max_webhook.router)

    def db_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = db_session
    monkeypatch.setattr(max_webhook, "settings", Settings(max_webhook_secret="test-secret"))
    monkeypatch.setattr(max_webhook, "send_callback_answer", lambda *_args: None)

    def update(action: str, user_id: int, callback_id: str) -> dict[str, object]:
        return {
            "update_type": "message_callback",
            "timestamp": 1750000000000,
            "callback": {
                "callback_id": callback_id,
                "payload": f"{action}:{dvizh_id}:{candidate_id}",
                "user": {"user_id": f"notify-{user_id}"},
            },
        }

    with TestClient(app) as client:
        headers = {"X-Max-Bot-Api-Secret": "test-secret"}
        for action, user_id, callback_id in (("reconfirm", 0, "yes"), ("withdraw", 1, "no")):
            body = update(action, user_id, callback_id)
            assert (
                client.post("/integrations/max/webhook", json=body, headers=headers).status_code
                == 200
            )
            assert (
                client.post("/integrations/max/webhook", json=body, headers=headers).status_code
                == 200
            )
    with Session(engine) as session:
        confirmations = list(session.scalars(select(DvizhConfirmation)))
        by_user = {confirmation.user_id: confirmation for confirmation in confirmations}
        users = list(session.scalars(select(User)))
        by_max = {user.max_user_id: by_user[user.id] for user in users}
        assert by_max["notify-0"].reconfirmed_at is not None
        assert by_max["notify-1"].status == "DECLINED"
        assert by_max["notify-2"].status == "CONFIRMED"
        assert len(_events(session, "DVIZH_WAITLIST_AVAILABLE")) == 1
    engine.dispose()
