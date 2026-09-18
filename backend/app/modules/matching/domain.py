"""Pure, deterministic matching primitives; no HTTP or ORM imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class CompatibilityResult:
    kind: str
    distance_km: float | None
    budget_delta: int | None


@dataclass(frozen=True)
class GroupSizeCandidate:
    """A privately eligible participant and their inclusive group-size range."""

    user_id: str
    min_people: int
    max_people: int | None


@dataclass(frozen=True)
class FeasibleCohort:
    """The size shared by every participant in the returned cohort."""

    size: int
    user_ids: tuple[str, ...]


def haversine_km(origin_lat: float, origin_lon: float, venue_lat: float, venue_lon: float) -> float:
    lat_delta = radians(venue_lat - origin_lat)
    lon_delta = radians(venue_lon - origin_lon)
    a = (
        sin(lat_delta / 2) ** 2
        + cos(radians(origin_lat)) * cos(radians(venue_lat)) * sin(lon_delta / 2) ** 2
    )
    return 6371.0088 * 2 * asin(sqrt(a))


def budget_compatibility(
    price: int | None, max_budget: int | None, near_limit: int
) -> tuple[str, int | None]:
    if max_budget is None:
        return "EXACT", None
    if price is None:
        return "UNVERIFIED", None
    if price <= max_budget:
        return "EXACT", None
    delta = price - max_budget
    if delta <= near_limit:
        return "NEAR", delta
    return "CONFLICT", delta


def compatibility(
    *,
    price: int | None,
    max_budget: int | None,
    near_limit: int,
    distance_km: float | None,
    radius_km: float | None,
) -> CompatibilityResult:
    budget_kind, delta = budget_compatibility(price, max_budget, near_limit)
    distance_kind = "EXACT"
    if radius_km is not None:
        if distance_km is None:
            distance_kind = "UNVERIFIED"
        elif distance_km > radius_km:
            distance_kind = "CONFLICT"
    if "CONFLICT" in (budget_kind, distance_kind):
        return CompatibilityResult("CONFLICT", distance_km, delta)
    if "UNVERIFIED" in (budget_kind, distance_kind):
        return CompatibilityResult("UNVERIFIED", distance_km, delta)
    if budget_kind == "NEAR":
        return CompatibilityResult("NEAR", distance_km, delta)
    return CompatibilityResult("EXACT", distance_km, None)


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    # SQLite returns naive datetimes even for timezone-aware columns. All stored
    # product times are UTC, so restore that invariant at this boundary.
    values = (start_a, end_a, start_b, end_b)
    normalized = tuple(
        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        for value in values
    )
    left_start, left_end, right_start, right_end = normalized
    return left_start < right_end and right_start < left_end


def contains_interval(
    available_from: datetime, available_to: datetime, starts_at: datetime, ends_at: datetime
) -> bool:
    """A fixed event must entirely fit the one-time availability interval."""
    values = (available_from, available_to, starts_at, ends_at)
    start_available, end_available, start_event, end_event = tuple(
        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        for value in values
    )
    return start_available <= start_event and end_event <= end_available


def recurring_interval_fits(
    *,
    starts_at: datetime,
    ends_at: datetime,
    weekdays: list[int],
    local_start: str,
    local_end: str,
    timezone_name: str,
) -> bool:
    """Match a complete event interval against one local weekly occurrence.

    The weekday names the local date on which the allowed window starts. A
    window whose end is not later than its start crosses into the following
    local day (for example Friday 22:00–02:00).
    """
    zone = ZoneInfo(timezone_name)
    event_start = starts_at.replace(tzinfo=UTC) if starts_at.tzinfo is None else starts_at.astimezone(UTC)
    event_end = ends_at.replace(tzinfo=UTC) if ends_at.tzinfo is None else ends_at.astimezone(UTC)
    if event_end <= event_start:
        return False
    local_event_start = event_start.astimezone(zone)
    local_event_end = event_end.astimezone(zone)
    if local_event_start.weekday() not in weekdays:
        return False
    start_hour, start_minute = (int(value) for value in local_start.split(":"))
    end_hour, end_minute = (int(value) for value in local_end.split(":"))
    window_start = datetime.combine(
        local_event_start.date(), time(start_hour, start_minute), tzinfo=zone
    )
    window_end = datetime.combine(local_event_start.date(), time(end_hour, end_minute), tzinfo=zone)
    if window_end <= window_start:
        window_end += timedelta(days=1)
    return window_start <= local_event_start and local_event_end <= window_end


def feasible_cohort(candidates: list[GroupSizeCandidate], maximum_size: int = 12) -> FeasibleCohort | None:
    """Find a deterministic group size satisfying every selected participant.

    The MVP preference is the smallest feasible final group so an otherwise
    ready plan does not wait for every compatible person. For a chosen size
    N, every returned participant has ``min_people <= N <= max_people`` and at
    least N eligible users exist. Sorting user ids makes the result independent
    of database/Intent enumeration order; higher-level presentation ranking may
    deterministically choose which N users receive the first private Offers.
    """
    unique = {candidate.user_id: candidate for candidate in candidates}
    for size in range(1, maximum_size + 1):
        cohort = sorted(
            candidate.user_id
            for candidate in unique.values()
            if candidate.min_people <= size and (candidate.max_people is None or size <= candidate.max_people)
        )
        if len(cohort) >= size:
            return FeasibleCohort(size=size, user_ids=tuple(cohort))
    return None


def offer_expiry(now: datetime, starts_at: datetime) -> datetime | None:
    """Give users time proportional to the remaining interval, with a start cutoff."""
    cutoff = starts_at - timedelta(minutes=10)
    if cutoff <= now:
        return None
    ttl = min(timedelta(hours=6), max(timedelta(minutes=10), (starts_at - now) / 2))
    return min(now + ttl, cutoff)


def confirmed_size(accepted: list[GroupSizeCandidate], group_size: int) -> int | None:
    """Return the accepted count only if every accepted person's range allows it."""
    count = len(accepted)
    if count < 2 or count > group_size:
        return None
    if all(candidate.min_people <= count <= (candidate.max_people or group_size) for candidate in accepted):
        return count
    return None
