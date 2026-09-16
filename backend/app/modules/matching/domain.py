"""Pure, deterministic matching primitives; no HTTP or ORM imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class CompatibilityResult:
    kind: str
    distance_km: float | None
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
    return start_a < end_b and start_b < end_a
