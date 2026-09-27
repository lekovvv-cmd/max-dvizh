import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from app import main
from app.api.routes import health
from app.core.config import Settings
from app.main import app


def test_healthcheck_returns_technical_status() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "version": "1.0.0",
    }


@pytest.mark.parametrize(
    "token,url,secret",
    [
        ("", "", ""),
        ("private-token", "", ""),
        ("private-token", "", "private-secret"),
        ("private-token", "https://example.org/webhook", ""),
    ],
)
def test_production_api_starts_and_is_ready_without_webhook(
    monkeypatch, caplog, token, url, secret
) -> None:
    settings = Settings(
        app_env="production",
        allow_demo_auth=False,
        database_url="postgresql://user:private-password@database/app",
        max_bot_token=token,
        max_webhook_url=url,
        max_webhook_secret=secret,
    )
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(health, "settings", settings)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(health, "engine", engine)
    try:
        with caplog.at_level(logging.WARNING), TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "ok"}
        assert "max_webhook_not_configured" in caplog.text
        assert "private-" not in caplog.text
    finally:
        engine.dispose()


def test_readiness_still_rejects_unavailable_database(monkeypatch) -> None:
    def unavailable():
        raise OperationalError("private-password", {}, Exception("unavailable"))

    monkeypatch.setattr(health.engine, "connect", unavailable)
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not ready"}
