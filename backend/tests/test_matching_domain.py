from datetime import UTC, datetime, timedelta

from app.modules.matching.domain import budget_compatibility, haversine_km, overlaps


def test_budget_exact_near_and_conflict() -> None:
    assert budget_compatibility(400, 500, 150) == ("EXACT", None)
    assert budget_compatibility(400, 300, 150) == ("NEAR", 100)
    assert budget_compatibility(500, 300, 150) == ("CONFLICT", 200)


def test_haversine_and_half_open_interval_overlap() -> None:
    assert round(haversine_km(55.7558, 37.6176, 55.7558, 37.6176), 2) == 0
    assert 600 < haversine_km(55.7558, 37.6176, 59.9343, 30.3351) < 700
    start = datetime(2026, 9, 16, 18, tzinfo=UTC)
    assert overlaps(
        start, start + timedelta(hours=2), start + timedelta(hours=1), start + timedelta(hours=3)
    )
    assert not overlaps(
        start, start + timedelta(hours=2), start + timedelta(hours=2), start + timedelta(hours=3)
    )
