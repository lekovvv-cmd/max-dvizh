"""Pure, deterministic matching primitives; no HTTP or ORM imports."""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class CompatibilityResult:
    kind: str
    distance_km: float
    budget_delta: int | None


def haversine_km(origin_lat: float, origin_lon: float, venue_lat: float, venue_lon: float) -> float:
    lat_delta = radians(venue_lat - origin_lat)
    lon_delta = radians(venue_lon - origin_lon)
    a = (
        sin(lat_delta / 2) ** 2
        + cos(radians(origin_lat)) * cos(radians(venue_lat)) * sin(lon_delta / 2) ** 2
    )
    return 6371.0088 * 2 * asin(sqrt(a))


def budget_compatibility(
    price: int | None, max_budget: int, near_limit: int
) -> tuple[str, int | None]:
    # A budget is a hard constraint in the current Signal schema.  Unknown
    # price cannot prove that constraint, so it is never silently Exact.
    if price is None:
        return "CONFLICT", None
    if price <= max_budget:
        return "EXACT", None
    delta = price - max_budget
    if delta <= near_limit:
        return "NEAR", delta
    return "CONFLICT", delta


def compatibility(
    *, price: int | None, max_budget: int, near_limit: int, distance_km: float, radius_km: float
) -> CompatibilityResult:
    if distance_km > radius_km:
        return CompatibilityResult("CONFLICT", distance_km, None)
    kind, delta = budget_compatibility(price, max_budget, near_limit)
    return CompatibilityResult(kind, distance_km, delta)


def overlaps(start_a: object, end_a: object, start_b: object, end_b: object) -> bool:
    return bool(start_a < end_b and start_b < end_a)
