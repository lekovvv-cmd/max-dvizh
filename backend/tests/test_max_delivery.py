"""Delivery diagnostics use mocked HTTP and local data, never real MAX accounts."""

import logging
import socket
import ssl
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.max_webhook import retry_notifications_after_bot_start
from app.core.config import Settings
from app.db.models import (
    Base,
    DvizhCandidate,
    DvizhSession,
    Group,
    GroupMember,
    Intent,
    OutboxNotification,
    User,
)
from app.modules.max_integration import client, diagnose
from app.modules.max_integration.diagnostics import classify_failure, failure_summary


@pytest.fixture
def delivery(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(client, "settings", Settings(max_bot_token="private-token"))
    with Session(engine) as session:
        user = User(max_user_id="private-user", display_name="Private Name")
        session.add(user)
        session.flush()
        group = Group(name="Private Group", created_by=user.id, default_city_slug="msk")
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
            signal_id=signal.id,
            group_id=group.id,
            initiator_id=user.id,
            status="COLLECTING_REACTIONS",
            activity_ids=["quest"],
            min_people=2,
            max_people=3,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
        session.add(dvizh)
        session.flush()
        session.add(
            DvizhCandidate(
                session_id=dvizh.id,
                position=0,
                provider="KUDAGO",
                provider_item_id="test",
                item_type="EVENT",
                title="Private Place",
                activity_ids=["quest"],
                starts_at=datetime.now(UTC) + timedelta(hours=1),
                ends_at=datetime.now(UTC) + timedelta(hours=2),
                compatibility="EXACT",
                seed=True,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        event = OutboxNotification(
            kind="DVIZH_REVIEW_REQUIRED",
            user_id=user.id,
            payload={"dvizh_id": dvizh.id},
            status="PENDING",
            next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.add(event)
        session.commit()
        yield session, event, dvizh
    engine.dispose()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
def test_delivery_status_retry_and_safe_logs(delivery, monkeypatch, caplog, status):
    session, event, _ = delivery
    request = httpx.Request(
        "POST",
        "https://platform-api2.max.ru/messages?user_id=private-user",
        headers={"Authorization": "private-token"},
    )
    response = httpx.Response(
        status,
        request=request,
        json={
            "code": "user.not.found",
            "message": "private-token private-user Private Name private-secret",
        },
    )

    def fail(*_args):
        raise httpx.HTTPStatusError(
            "private-token private-user", request=request, response=response
        )

    monkeypatch.setattr(client, "send_dvizh_message", fail)
    with caplog.at_level(logging.WARNING):
        assert client.dispatch_pending(session) == 0
    retry = status == 429 or status >= 500
    assert event.status == ("PENDING" if retry else "FAILED")
    assert event.attempts == 1
    assert event.locked_at is None
    assert (event.next_attempt_at is not None) == retry
    assert f"id={event.id}" in caplog.text
    assert "kind=DVIZH_REVIEW_REQUIRED" in caplog.text
    assert f"http_status={status}" in caplog.text
    assert "error_class=HTTPStatusError" in caplog.text
    assert 'response_body={"code":"user.not.found"}' in caplog.text
    assert all(
        value not in caplog.text
        for value in ["private-token", "private-user", "Private Name", "private-secret"]
    )
    assert client.dispatch_pending(session) == 0  # terminal or future backoff
    assert event.attempts == 1


@pytest.mark.parametrize(
    "error,reason",
    [
        (httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] private-token"), "tls"),
        (httpx.ConnectError("getaddrinfo failed private-token"), "dns"),
        (httpx.ConnectTimeout("private-token"), "connect_timeout"),
        (httpx.ReadTimeout("private-token"), "read_timeout"),
        (httpx.ConnectError("private-token"), "connect"),
        (httpx.RemoteProtocolError("private-token"), "transport"),
    ],
)
def test_transport_classification_is_safe_and_retryable(error, reason):
    failure = classify_failure(error)
    assert failure.reason == reason
    assert failure.retryable
    assert failure.http_status is None
    assert "private-token" not in failure_summary(failure)


@pytest.mark.parametrize(
    "cause,reason", [(ssl.SSLError("secret"), "tls"), (socket.gaierror("secret"), "dns")]
)
def test_wrapped_os_errors_are_classified(cause, reason):
    error = httpx.ConnectError("connection failed")
    error.__cause__ = cause
    assert classify_failure(error).reason == reason


def test_eighth_attempt_is_terminal_and_bot_start_reopens_only_current(delivery, monkeypatch):
    session, event, dvizh = delivery
    event.attempts = 7
    session.commit()

    def fail(*_args):
        raise httpx.ReadTimeout("private-token")

    monkeypatch.setattr(client, "send_dvizh_message", fail)
    assert client.dispatch_pending(session) == 0
    assert event.status == "FAILED" and event.attempts == 8
    assert event.next_attempt_at is None
    assert client.dispatch_pending(session) == 0
    retry_notifications_after_bot_start(session, event.user_id)
    assert event.status == "PENDING" and event.attempts == 0
    assert event.next_attempt_at is None
    event.status = "FAILED"
    dvizh.status = "EXPIRED"
    session.commit()
    retry_notifications_after_bot_start(session, event.user_id)
    assert event.status == "CANCELLED"


def test_success_counts_attempt_and_clears_backoff(delivery, monkeypatch):
    session, event, _ = delivery
    monkeypatch.setattr(client, "send_dvizh_message", lambda *_args: True)
    assert client.dispatch_pending(session) == 1
    assert event.status == "SENT" and event.attempts == 1
    assert event.sent_at is not None
    sent_at = event.sent_at
    assert client.dispatch_pending(session) == 0
    assert event.sent_at == sent_at
    assert event.next_attempt_at is None and event.locked_at is None


def test_stale_notification_cancels_without_attempt(delivery):
    session, event, dvizh = delivery
    dvizh.status = "EXPIRED"
    session.commit()
    assert client.dispatch_pending(session) == 0
    assert event.status == "CANCELLED" and event.attempts == 0
    assert event.next_attempt_at is None


def test_diagnose_checks_only_me_and_never_prints_identity(monkeypatch, capsys):
    monkeypatch.setattr(diagnose, "settings", Settings(max_bot_token="private-token"))

    def get(url, **kwargs):
        assert url == "https://platform-api2.max.ru/me"
        assert kwargs["headers"] == {"Authorization": "private-token"}
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={"is_bot": True, "user_id": "private-user", "first_name": "Private Name"},
        )

    monkeypatch.setattr(diagnose.httpx, "get", get)
    assert diagnose.main() == 0
    output = capsys.readouterr().out
    assert "success=true http_status=200" in output
    assert "MAX_BOT_TOKEN_set=True" in output
    assert all(value not in output for value in ["private-token", "private-user", "Private Name"])


def test_diagnose_fails_safely_without_token_or_on_transport_error(monkeypatch, capsys):
    monkeypatch.setattr(diagnose, "settings", Settings(max_bot_token=""))
    assert diagnose.main() == 1
    assert "MAX_BOT_TOKEN_set=False" in capsys.readouterr().out
    monkeypatch.setattr(diagnose, "settings", Settings(max_bot_token="private-token"))

    def get(*_args, **_kwargs):
        raise httpx.ConnectTimeout("private-token")

    monkeypatch.setattr(diagnose.httpx, "get", get)
    assert diagnose.main() == 1
    output = capsys.readouterr().out
    assert "error_class=ConnectTimeout" in output
    assert "private-token" not in output
