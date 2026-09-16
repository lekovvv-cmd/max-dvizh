from datetime import UTC, datetime

from app.modules.leisure.provider import normalize_event


def test_provider_end_is_preserved_and_missing_end_uses_two_hour_fallback() -> None:
    fetched = datetime(2026, 9, 16, tzinfo=UTC)
    explicit = normalize_event({"id": 1, "dates": [{"start": 1_789_600_000, "end": 1_789_603_600}]}, "ekb", fetched)
    fallback = normalize_event({"id": 2, "dates": [{"start": 1_789_600_000}]}, "ekb", fetched)
    assert explicit is not None and explicit.ends_at.timestamp() == 1_789_603_600
    assert fallback is not None and fallback.ends_at.timestamp() == 1_789_607_200


def test_provider_discards_missing_or_invalid_dates_and_uses_first_valid_entry() -> None:
    fetched = datetime(2026, 9, 16, tzinfo=UTC)
    assert normalize_event({"id": 1, "dates": []}, "ekb", fetched) is None
    assert normalize_event({"id": 1, "dates": [{"start": 10, "end": 10}]}, "ekb", fetched) is None
    item = normalize_event({"id": 1, "dates": [{}, {"start": 1_789_600_000, "end": 1_789_603_600}]}, "ekb", fetched)
    assert item is not None and item.starts_at.timestamp() == 1_789_600_000
