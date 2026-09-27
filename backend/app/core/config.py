import re
from dataclasses import dataclass
from os import getenv
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class ConfigurationError(ValueError):
    """A safe configuration error containing variable names, never their values."""


def normalize_database_url(value: str) -> str:
    """Select psycopg 3 when a provider returns a driver-neutral PostgreSQL URL."""
    for scheme in ("postgres://", "postgresql://"):
        if value.startswith(scheme):
            return value.replace(scheme, "postgresql+psycopg://", 1)
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str = "MAX ДВИЖ API"
    app_version: str = "1.0.0"
    app_env: str = getenv("APP_ENV", "production")
    allow_demo_auth: bool = getenv("ALLOW_DEMO_AUTH", "false").lower() == "true"
    database_url: str = getenv("DATABASE_URL", "")
    max_bot_token: str = getenv("MAX_BOT_TOKEN", "")
    max_bot_api_base: str = getenv("MAX_BOT_API_BASE", "https://platform-api2.max.ru")
    max_bot_username: str = getenv("MAX_BOT_USERNAME", "")
    max_mini_app_url: str = getenv("MAX_MINI_APP_URL", "")
    max_webhook_url: str = getenv("MAX_WEBHOOK_URL", "")
    max_webhook_secret: str = getenv("MAX_WEBHOOK_SECRET", "")
    kudago_base_url: str = getenv("KUDAGO_BASE_URL", "https://kudago.com/public-api/v1.4")
    kudago_timeout_seconds: float = float(getenv("KUDAGO_TIMEOUT_SECONDS", "5"))
    redis_url: str = getenv("REDIS_URL", "")
    near_budget_max_delta_rub: int = int(getenv("NEAR_BUDGET_MAX_DELTA_RUB", "150"))
    leisure_cache_ttl_seconds: int = int(getenv("LEISURE_CACHE_TTL_SECONDS", "900"))
    kudago_max_pages: int = int(getenv("KUDAGO_MAX_PAGES", "3"))
    place_plan_duration_minutes: int = int(getenv("PLACE_PLAN_DURATION_MINUTES", "120"))
    autosignal_poll_seconds: int = int(getenv("AUTOSIGNAL_POLL_SECONDS", "1800"))
    autosignal_lookahead_days: int = int(getenv("AUTOSIGNAL_LOOKAHEAD_DAYS", "7"))
    outbox_poll_seconds: float = float(getenv("OUTBOX_POLL_SECONDS", "5"))
    outbox_retry_max_seconds: int = int(getenv("OUTBOX_RETRY_MAX_SECONDS", "300"))
    max_init_data_age_seconds: int = int(getenv("MAX_INIT_DATA_MAX_AGE_SECONDS", "3600"))

    def __post_init__(self) -> None:
        database_url = self.database_url.strip()
        if not database_url and self.app_env == "development":
            database_url = (
                "postgresql+psycopg://max_dvizh:local_development_only@postgres:5432/max_dvizh"
            )
        object.__setattr__(self, "database_url", normalize_database_url(database_url))

    def validate_database(self) -> None:
        if not self.database_url:
            raise ConfigurationError("DATABASE_URL is required; use the same database as the API")
        try:
            url = make_url(self.database_url)
        except (ArgumentError, ValueError):
            raise ConfigurationError("DATABASE_URL is invalid; check its format") from None
        if self.app_env != "development" and (
            url.drivername != "postgresql+psycopg"
            or not url.database
            or not (url.host or url.query.get("host"))
        ):
            raise ConfigurationError("DATABASE_URL must specify a PostgreSQL host and database")

    def validate_webhook(self) -> None:
        if not self.max_bot_token or not self.max_webhook_url or not self.max_webhook_secret:
            raise ConfigurationError("Set MAX_BOT_TOKEN, MAX_WEBHOOK_URL and MAX_WEBHOOK_SECRET")
        try:
            url = urlsplit(self.max_webhook_url)
            valid = (
                url.scheme == "https"
                and bool(url.hostname)
                and url.port in {None, 443}
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ConfigurationError("MAX_WEBHOOK_URL must be a public HTTPS URL on port 443")
        if not re.fullmatch(r"[A-Za-z0-9_-]{5,256}", self.max_webhook_secret):
            raise ConfigurationError("MAX_WEBHOOK_SECRET must match the MAX subscription contract")

    def validate_process(self, process: str) -> None:
        if process not in {"api", "worker", "scheduler"}:
            raise ConfigurationError("APP_PROCESS must be api, worker or scheduler")
        self.validate_database()
        if self.app_env == "development":
            return
        if self.allow_demo_auth:
            raise ConfigurationError("ALLOW_DEMO_AUTH must be false in production")
        if process == "api":
            self.validate_webhook()
        elif process == "worker" and not self.max_bot_token:
            raise ConfigurationError("MAX_BOT_TOKEN is required for APP_PROCESS=worker")

    @property
    def local_demo_mode(self) -> bool:
        return self.app_env == "development" and self.allow_demo_auth


settings = Settings()


if __name__ == "__main__":
    try:
        settings.validate_process(getenv("APP_PROCESS", "api"))
    except ConfigurationError as error:
        raise SystemExit(str(error)) from None
