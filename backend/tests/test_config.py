from app.core.config import normalize_database_url


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
