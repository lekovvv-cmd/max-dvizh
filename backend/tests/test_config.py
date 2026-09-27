import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.core.config import ConfigurationError, Settings, normalize_database_url
from app.modules.matching import scheduler


def test_normalize_database_url_selects_psycopg_for_provider_urls() -> None:
    assert (
        normalize_database_url("postgresql://user:password@db:5432/app")
        == "postgresql+psycopg://user:password@db:5432/app"
    )
    assert (
        normalize_database_url("postgres://user:password@db:5432/app")
        == "postgresql+psycopg://user:password@db:5432/app"
    )


def test_normalize_database_url_keeps_explicit_driver() -> None:
    url = "postgresql+psycopg://user:password@db:5432/app"
    assert normalize_database_url(url) == url


def production(**overrides: object) -> Settings:
    values = dict(
        app_env="production",
        allow_demo_auth=False,
        database_url="postgresql://user:private-password@database/app",
        max_bot_token="private-token",
        max_webhook_url="https://example.org/api/v1/integrations/max/webhook",
        max_webhook_secret="private-secret",
        max_bot_username="",
    )
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize("process", ["api", "worker", "scheduler"])
def test_production_requires_explicit_database_url(process: str) -> None:
    settings = production(database_url="")
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        settings.validate_process(process)
    assert settings.database_url == ""


def test_database_default_is_development_only_and_api_username_is_optional() -> None:
    assert "@postgres:" in Settings(app_env="development", database_url="").database_url
    production().validate_process("api")


@pytest.mark.parametrize("field", ["max_bot_token", "max_webhook_url", "max_webhook_secret"])
def test_api_rejects_missing_webhook_configuration(field: str) -> None:
    with pytest.raises(ConfigurationError, match="MAX_") as error:
        production(**{field: ""}).validate_process("api")
    assert "private-" not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/hook",
        "https://example.org:8443/hook",
        "https://example.org:bad/hook",
        "https://user:secret@example.org/hook",
    ],
)
def test_webhook_rejects_invalid_urls_without_echoing_them(url: str) -> None:
    with pytest.raises(ConfigurationError) as error:
        production(max_webhook_url=url).validate_webhook()
    assert url not in str(error.value)


def test_background_processes_do_not_require_unused_webhook_settings() -> None:
    production(max_webhook_url="", max_webhook_secret="").validate_process("worker")
    production(max_webhook_url="", max_webhook_secret="", max_bot_token="").validate_process(
        "scheduler"
    )
    with pytest.raises(ConfigurationError, match="MAX_BOT_TOKEN"):
        production(max_bot_token="").validate_process("worker")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://user:private-password@db:bad/app",
        "postgresql://",
        "sqlite:///private-password.db",
    ],
)
def test_scheduler_rejects_malformed_database_without_exposing_credentials(url: str) -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_URL") as error:
        production(database_url=url).validate_process("scheduler")
    assert "private-password" not in str(error.value)


def test_scheduler_checks_database_and_logs_only_safe_startup_status(monkeypatch, caplog) -> None:
    monkeypatch.setattr(scheduler, "settings", production())
    monkeypatch.setattr(scheduler, "engine", create_engine("sqlite://"))
    with caplog.at_level(logging.INFO):
        scheduler.startup()
    assert "scheduler_started mode=production database_connected=true" in caplog.text
    assert "private-" not in caplog.text

    def unavailable():
        raise OperationalError("private-password", {}, Exception("private-token"))

    monkeypatch.setattr(scheduler.engine, "connect", unavailable)
    with pytest.raises(SystemExit, match="database_connected=false") as error:
        scheduler.startup()
    assert "private-" not in str(error.value)
