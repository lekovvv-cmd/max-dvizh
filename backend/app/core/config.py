from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "MAX ДВИЖ API"
    app_version: str = "0.1.0"
    database_url: str = getenv(
        "DATABASE_URL",
        "postgresql+psycopg://max_dvizh:local_development_only@postgres:5432/max_dvizh",
    )


settings = Settings()
