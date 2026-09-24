"""Signed MAX callbacks are replay-safe and never need Mini App initData."""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes import max_webhook
from app.core.config import Settings
from app.db.models import (
    Base,
    DvizhCandidate,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    MaxWebhookEvent,
    OutboxNotification,
    User,
)
from app.db.session import get_session
from app.modules.max_integration import client as max_client
from app.modules.max_integration import subscribe_webhook


def test_webhook_secret_and_duplicate_bot_start(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(max_webhook.router)

    def db_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = db_session
    monkeypatch.setattr(max_webhook, "settings", Settings(max_webhook_secret="test-secret"))
    update = {
        "update_type": "bot_started",
        "timestamp": 1750000000000,
        "chat_id": 5,
        "user": {"user_id": 123, "name": "Антон"},
    }
    with TestClient(app) as client:
        assert client.post("/integrations/max/webhook", json=update).status_code == 403
        headers = {"X-Max-Bot-Api-Secret": "test-secret"}
        assert (
            client.post("/integrations/max/webhook", json=update, headers=headers).status_code
            == 200
        )
        assert (
            client.post("/integrations/max/webhook", json=update, headers=headers).status_code
            == 200
        )
        new_start = {**update, "timestamp": 1750000000001}
        assert (
            client.post("/integrations/max/webhook", json=new_start, headers=headers).status_code
            == 200
        )
        callback = {
            "update_type": "message_callback",
            "timestamp": 1750000000002,
            "callback": {
                "callback_id": "click-1",
                "payload": "confirm:missing:old-candidate",
                "user": {"user_id": 123},
            },
        }
        assert (
            client.post("/integrations/max/webhook", json=callback, headers=headers).status_code
            == 200
        )
        assert (
            client.post("/integrations/max/webhook", json=callback, headers=headers).status_code
            == 200
        )
    with Session(engine) as session:
        assert len(list(session.scalars(select(User)))) == 1
        assert len(list(session.scalars(select(MaxWebhookEvent)))) == 3
        events = list(session.scalars(select(OutboxNotification)))
        assert {event.kind for event in events} == {"MAX_WELCOME", "MAX_CALLBACK_ANSWER"}
        assert len(events) == 2


def test_max_outbox_buttons_use_callback_only_for_exact_match(monkeypatch) -> None:
    sent = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": True}

    def post(url, **kwargs):
        sent.append((url, kwargs))
        return Response()

    monkeypatch.setattr(
        max_client, "settings", Settings(max_bot_token="test-token", max_bot_username="DvizhBot")
    )
    monkeypatch.setattr(max_client.httpx, "post", post)
    common = {
        "dvizh_id": "d1",
        "candidate_id": "c1",
        "activity_ids": ["quest"],
        "title": "Квест",
    }
    exact = OutboxNotification(
        kind="DVIZH_MATCH_FOUND",
        user_id="u1",
        payload={**common, "compatibility": "EXACT"},
        status="PENDING",
    )
    near = OutboxNotification(
        kind="DVIZH_MATCH_FOUND",
        user_id="u1",
        payload={**common, "compatibility": "NEAR"},
        status="PENDING",
    )
    max_client.send_dvizh_message("123", exact)
    max_client.send_dvizh_message("123", near)
    max_client.send_welcome("123")
    max_client.send_callback_answer("click-1", "Сохранено")
    buttons = [call[1]["json"]["attachments"][0]["payload"]["buttons"][0][0] for call in sent[:3]]
    assert buttons[0] == {"type": "callback", "text": "Я в деле", "payload": "confirm:d1:c1"}
    assert buttons[1]["type"] == "link" and "startapp=dvizh_d1" in buttons[1]["url"]
    assert buttons[2]["text"] == "Открыть ДВИЖ"
    assert buttons[2]["url"] == "https://max.ru/DvizhBot?startapp"
    assert sent[3][1]["json"] == {"notification": "Сохранено"}
    assert all(call[1]["headers"]["Authorization"] == "test-token" for call in sent)


def test_subscription_setup_posts_and_verifies_official_contract(monkeypatch) -> None:
    calls = []
    url = "https://api.example.org/api/v1/integrations/max/webhook"

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class Client:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, path, **kwargs):
            calls.append(("post", path, kwargs))
            return Response({"success": True})

        def get(self, path):
            calls.append(("get", path))
            return Response(
                {"subscriptions": [{"url": url, "update_types": subscribe_webhook.UPDATE_TYPES}]}
            )

    monkeypatch.setattr(
        subscribe_webhook,
        "settings",
        Settings(
            max_bot_token="test-token",
            max_webhook_url=url,
            max_webhook_secret="valid-secret",
        ),
    )
    monkeypatch.setattr(subscribe_webhook.httpx, "Client", Client)
    subscribe_webhook.subscribe()
    assert calls[0][1]["headers"] == {"Authorization": "test-token"}
    assert calls[1][2]["json"] == {
        "url": url,
        "update_types": ["bot_started", "message_callback", "bot_removed"],
        "secret": "valid-secret",
    }
    assert calls[2] == ("get", "/subscriptions")


def test_worker_delivers_new_dvizh_outbox_event(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    delivered = []
    monkeypatch.setattr(max_client, "settings", Settings(max_bot_token="test-token"))
    monkeypatch.setattr(
        max_client,
        "send_dvizh_message",
        lambda max_user_id, event: delivered.append((max_user_id, event.kind)),
    )
    with Session(engine) as session:
        user = User(max_user_id="123", display_name="Антон")
        session.add(user)
        session.flush()
        group = Group(name="Компания", default_city_slug="msk", created_by=user.id)
        session.add(group)
        session.flush()
        session.add(GroupMember(group_id=group.id, user_id=user.id))
        signal = Intent(
            user_id=user.id,
            group_id=group.id,
            type="ONE_TIME",
            city_slug="msk",
            activity_category="quest",
            min_people=2,
        )
        session.add(signal)
        session.flush()
        dvizh = DvizhSession(
            id="d1",
            signal_id=signal.id,
            group_id=group.id,
            initiator_id=user.id,
            status="COLLECTING_REACTIONS",
            activity_ids=["quest"],
            min_people=2,
            max_people=2,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
        session.add(dvizh)
        start = datetime.now(UTC) + timedelta(hours=1)
        candidate = DvizhCandidate(
            session_id=dvizh.id,
            position=0,
            provider="KUDAGO",
            provider_item_id="42",
            item_type="EVENT",
            title="Квест",
            activity_ids=["quest"],
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            compatibility="EXACT",
            seed=True,
            expires_at=start - timedelta(minutes=10),
        )
        session.add(candidate)
        event = OutboxNotification(
            kind="DVIZH_REVIEW_REQUIRED",
            user_id=user.id,
            payload={"dvizh_id": "d1", "activity_ids": ["quest"]},
            status="PENDING",
        )
        session.add(event)
        session.commit()
        assert max_client.dispatch_pending(session) == 1
        assert delivered == [("123", "DVIZH_REVIEW_REQUIRED")]
        assert session.get(OutboxNotification, event.id).status == "SENT"
        dvizh.status = "EXPIRED"
        stale = OutboxNotification(
            kind="DVIZH_REVIEW_REQUIRED",
            user_id=user.id,
            payload={"dvizh_id": dvizh.id, "activity_ids": ["quest"]},
            status="PENDING",
        )
        session.add(stale)
        session.commit()
        assert max_client.dispatch_pending(session) == 0
        assert stale.status == "CANCELLED"
        assert delivered == [("123", "DVIZH_REVIEW_REQUIRED")]
        dvizh.status = "AWAITING_CONFIRMATION"
        dvizh.active_candidate_id = None  # fallback superseded the old match
        old_match = OutboxNotification(
            kind="DVIZH_MATCH_FOUND",
            user_id=user.id,
            payload={"dvizh_id": dvizh.id, "candidate_id": candidate.id},
            status="PENDING",
        )
        session.add(old_match)
        session.commit()
        assert max_client.dispatch_pending(session) == 0
        assert old_match.status == "CANCELLED"
