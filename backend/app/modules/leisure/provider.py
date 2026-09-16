"""KudaGo adapter with a Redis-only external catalogue cache.

Provider records are deliberately plain normalized DTOs. They never become
PostgreSQL rows unless matching creates a CandidatePlan, at which point the
plan receives its own immutable source snapshot.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx
import redis

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class NormalizedLeisureItem:
    provider: str
    provider_id: str
    item_type: str
    city_slug: str
    title: str
    category: str
    venue_name: str | None
    starts_at: datetime
    ends_at: datetime
    latitude: float | None
    longitude: float | None
    price_text: str | None
    price_min: int | None
    source_url: str | None
    image_url: str | None
    source_fetched_at: datetime
    is_demo: bool = False

    def to_cache(self) -> dict[str, object]:
        result = asdict(self)
        for field in ("starts_at", "ends_at", "source_fetched_at"):
            result[field] = getattr(self, field).isoformat()
        return result

    @classmethod
    def from_cache(cls, value: dict[str, object]) -> NormalizedLeisureItem:
        converted = dict(value)
        for field in ("starts_at", "ends_at", "source_fetched_at"):
            converted[field] = datetime.fromisoformat(str(converted[field]))
        return cls(**converted)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ProviderResult:
    items: list[NormalizedLeisureItem]
    cached: bool
    fetched_at: datetime | None
    unavailable: bool = False


def parse_price(value: str | None, is_free: bool) -> int | None:
    if is_free:
        return 0
    if not value:
        return None
    numbers = re.findall(r"(?<!\d)(\d{1,6})(?!\d)", value.replace(" ", ""))
    return int(numbers[0]) if len(numbers) == 1 else None


def normalize_event(raw: dict[str, Any], city: str, fetched_at: datetime) -> NormalizedLeisureItem | None:
    dates = raw.get("dates") or []
    date = next((item for item in dates if item.get("start")), None)
    if date is None:
        return None
    start = datetime.fromtimestamp(int(date["start"]), UTC)
    end = datetime.fromtimestamp(int(date.get("end") or date["start"]) + 7200, UTC)
    place = raw.get("place") or {}
    coords = place.get("coords") or raw.get("coords") or {}
    categories = raw.get("categories") or []
    price_text = raw.get("price") or None
    free = bool(raw.get("is_free", False))
    return NormalizedLeisureItem(
        provider="KUDAGO",
        provider_id=str(raw["id"]),
        item_type="EVENT",
        city_slug=city,
        title=str(raw.get("title") or "Событие KudaGo"),
        category=str(categories[0] if categories else "other"),
        venue_name=place.get("title"),
        latitude=coords.get("lat"),
        longitude=coords.get("lon"),
        starts_at=start,
        ends_at=end,
        price_text=price_text,
        price_min=parse_price(price_text, free),
        source_url=raw.get("site_url"),
        image_url=((raw.get("images") or [{}])[0] or {}).get("image"),
        source_fetched_at=fetched_at,
    )


class RedisProviderCache:
    """Small cache module, intentionally not a separate infrastructure layer."""

    def __init__(self, client: redis.Redis[str] | None = None) -> None:
        self.client = client or redis.Redis.from_url(settings.redis_url, decode_responses=True)

    @staticmethod
    def events_key(city: str, date_range: str = "future", categories: tuple[str, ...] = ()) -> str:
        category_hash = sha256(",".join(sorted(categories)).encode()).hexdigest()[:12]
        return f"kudago:events:{city}:{date_range}:{category_hash}"

    def get_events(self, city: str) -> list[NormalizedLeisureItem] | None:
        try:
            payload = self.client.get(self.events_key(city))
        except redis.RedisError:
            return None
        if payload is None:
            return None
        try:
            return [NormalizedLeisureItem.from_cache(item) for item in json.loads(payload)]
        except (TypeError, ValueError, KeyError):
            return None

    def set_events(self, city: str, items: list[NormalizedLeisureItem]) -> None:
        try:
            self.client.setex(
                self.events_key(city),
                settings.leisure_cache_ttl_seconds,
                json.dumps([item.to_cache() for item in items]),
            )
        except redis.RedisError:
            # The live provider response is still usable; cache outages never create demo data.
            return


class KudaGoProvider:
    def cities(self) -> list[dict[str, str]]:
        response = httpx.get(
            f"{settings.kudago_base_url}/locations/",
            params={"lang": "ru"},
            timeout=settings.kudago_timeout_seconds,
        )
        response.raise_for_status()
        return [{"slug": str(city["slug"]), "name": str(city["name"])} for city in response.json()]

    def items(self, city: str) -> list[NormalizedLeisureItem]:
        fetched_at = utcnow()
        response = httpx.get(
            f"{settings.kudago_base_url}/events/",
            params={
                "location": city,
                "actual_since": int(fetched_at.timestamp()),
                "page_size": 100,
                "fields": "id,title,dates,place,categories,price,is_free,site_url,images",
            },
            timeout=settings.kudago_timeout_seconds,
        )
        response.raise_for_status()
        return [
            item
            for raw in response.json().get("results", [])
            if (item := normalize_event(raw, city, fetched_at)) is not None
        ]


def fetch_city_items(
    city: str, *, provider: KudaGoProvider | None = None, cache: RedisProviderCache | None = None
) -> ProviderResult:
    """Use Redis first; on a miss, fetch KudaGo. Never fall back to PostgreSQL."""
    cache = cache or RedisProviderCache()
    cached = cache.get_events(city)
    if cached is not None:
        return ProviderResult(cached, cached=True, fetched_at=cached[0].source_fetched_at if cached else None)
    try:
        items = (provider or KudaGoProvider()).items(city)
    except (httpx.HTTPError, ValueError):
        # A second read lets a value written by another request win a race with failure.
        cached = cache.get_events(city)
        if cached is not None:
            return ProviderResult(cached, cached=True, fetched_at=cached[0].source_fetched_at if cached else None)
        return ProviderResult([], cached=False, fetched_at=None, unavailable=True)
    cache.set_events(city, items)
    return ProviderResult(items, cached=False, fetched_at=items[0].source_fetched_at if items else utcnow())
