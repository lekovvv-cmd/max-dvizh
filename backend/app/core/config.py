from dataclasses import dataclass
from os import getenv


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
    app_env: str = getenv("APP_ENV", "development")
    database_url: str = normalize_database_url(
        getenv(
            "DATABASE_URL",
            "postgresql+psycopg://max_dvizh:local_development_only@postgres:5432/max_dvizh",
        )
    )
    max_bot_token: str = getenv("MAX_BOT_TOKEN", "")
    max_bot_api_base: str = getenv("MAX_BOT_API_BASE", "https://platform-api2.max.ru")
    max_bot_username: str = getenv("MAX_BOT_USERNAME", "")
    max_mini_app_url: str = getenv("MAX_MINI_APP_URL", "")
    kudago_base_url: str = getenv("KUDAGO_BASE_URL", "https://kudago.com/public-api/v1.4")
    kudago_timeout_seconds: float = float(getenv("KUDAGO_TIMEOUT_SECONDS", "5"))
    redis_url: str = getenv("REDIS_URL", "redis://redis:6379/0")
    near_budget_max_delta_rub: int = int(getenv("NEAR_BUDGET_MAX_DELTA_RUB", "150"))
    leisure_cache_ttl_seconds: int = int(getenv("LEISURE_CACHE_TTL_SECONDS", "900"))
    kudago_max_pages: int = int(getenv("KUDAGO_MAX_PAGES", "3"))
    place_plan_duration_minutes: int = int(getenv("PLACE_PLAN_DURATION_MINUTES", "120"))
    autosignal_poll_seconds: int = int(getenv("AUTOSIGNAL_POLL_SECONDS", "1800"))
    autosignal_lookahead_days: int = int(getenv("AUTOSIGNAL_LOOKAHEAD_DAYS", "7"))
    outbox_poll_seconds: float = float(getenv("OUTBOX_POLL_SECONDS", "5"))
    outbox_retry_max_seconds: int = int(getenv("OUTBOX_RETRY_MAX_SECONDS", "300"))
    max_init_data_age_seconds: int = int(getenv("MAX_INIT_DATA_MAX_AGE_SECONDS", "3600"))


settings = Settings()
