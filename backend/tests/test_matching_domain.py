from datetime import UTC, datetime, timedelta

from app.modules.matching.domain import (
    GroupSizeCandidate,
    budget_compatibility,
    compatibility,
    contains_interval,
    feasible_cohort,
    haversine_km,
    overlaps,
    recurring_interval_fits,
)


def test_budget_exact_near_and_conflict() -> None:
    assert budget_compatibility(400, 500, 150) == ("EXACT", None)
    assert budget_compatibility(400, 300, 150) == ("NEAR", 100)
    assert budget_compatibility(500, 300, 150) == ("CONFLICT", 200)
    assert budget_compatibility(None, 300, 150) == ("UNVERIFIED", None)
    assert budget_compatibility(None, None, 150) == ("EXACT", None)


def test_optional_constraints_distinguish_conflict_from_unverified() -> None:
    assert (
        compatibility(
            price=None, max_budget=500, near_limit=150, distance_km=1, radius_km=None
        ).kind
        == "UNVERIFIED"
    )
    assert (
        compatibility(
            price=400, max_budget=None, near_limit=150, distance_km=None, radius_km=10
        ).kind
        == "UNVERIFIED"
    )
    assert (
        compatibility(
            price=400, max_budget=None, near_limit=150, distance_km=None, radius_km=None
        ).kind
        == "EXACT"
    )
    assert (
        compatibility(
            price=800, max_budget=500, near_limit=150, distance_km=None, radius_km=10
        ).kind
        == "CONFLICT"
    )


def test_haversine_and_half_open_interval_overlap() -> None:
    assert round(haversine_km(55.7558, 37.6176, 55.7558, 37.6176), 2) == 0
    assert 600 < haversine_km(55.7558, 37.6176, 59.9343, 30.3351) < 700
    start = datetime(2026, 9, 16, 18, tzinfo=UTC)
    assert overlaps(
        start, start + timedelta(hours=2), start + timedelta(hours=1), start + timedelta(hours=3)
    )


def test_group_feasibility_requires_every_participant_to_allow_exact_n() -> None:
    candidates = [
        GroupSizeCandidate("a", 2, 6),
        GroupSizeCandidate("b", 5, 5),
        GroupSizeCandidate("c", 4, 7),
        GroupSizeCandidate("d", 5, 12),
        GroupSizeCandidate("e", 3, 5),
    ]
    result = feasible_cohort(candidates)

    assert result is not None
    assert result.size == 5
    assert set(result.user_ids) == {"a", "b", "c", "d", "e"}
    assert feasible_cohort(list(reversed(candidates))) == result


def test_exact_five_never_has_false_smaller_confirmation_or_incompatible_plan() -> None:
    exact_five = [GroupSizeCandidate(str(index), 5, 5) for index in range(5)]
    assert feasible_cohort(exact_five[:4]) is None
    assert feasible_cohort(exact_five).size == 5  # type: ignore[union-attr]
    assert feasible_cohort([GroupSizeCandidate("a", 2, 2), GroupSizeCandidate("b", 3, 3)]) is None


def test_group_feasibility_prefers_fastest_valid_minimum_not_largest_cohort() -> None:
    result = feasible_cohort([GroupSizeCandidate(str(index), 2, 6) for index in range(6)])
    assert result is not None
    assert result.size == 2


def test_one_time_event_must_be_contained_not_merely_overlap() -> None:
    start = datetime(2026, 9, 18, 18, tzinfo=UTC)
    assert contains_interval(
        start, start + timedelta(hours=3), start + timedelta(hours=2), start + timedelta(hours=3)
    )
    assert not contains_interval(
        start, start + timedelta(hours=3), start + timedelta(hours=2), start + timedelta(hours=5)
    )


def test_recurring_time_timezone_and_overnight_window() -> None:
    # 15:00 UTC is 20:00 in Yekaterinburg on Friday.
    start = datetime(2026, 9, 18, 15, tzinfo=UTC)
    assert recurring_interval_fits(
        starts_at=start,
        ends_at=start + timedelta(hours=2),
        weekdays=[4],
        local_start="18:00",
        local_end="23:00",
        timezone_name="Asia/Yekaterinburg",
    )
    assert not recurring_interval_fits(
        starts_at=start - timedelta(hours=10),
        ends_at=start - timedelta(hours=8),
        weekdays=[4],
        local_start="18:00",
        local_end="23:00",
        timezone_name="Asia/Yekaterinburg",
    )
    overnight = datetime(2026, 9, 18, 17, tzinfo=UTC)  # Friday 22:00 local
    assert recurring_interval_fits(
        starts_at=overnight,
        ends_at=overnight + timedelta(hours=3),
        weekdays=[4],
        local_start="22:00",
        local_end="02:00",
        timezone_name="Asia/Yekaterinburg",
    )
    assert not overlaps(
        start, start + timedelta(hours=2), start + timedelta(hours=2), start + timedelta(hours=3)
    )
    assert overlaps(
        start.replace(tzinfo=None),
        (start + timedelta(hours=2)).replace(tzinfo=None),
        start + timedelta(hours=1),
        start + timedelta(hours=3),
    )
