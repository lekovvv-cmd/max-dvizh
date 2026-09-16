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
from typing import Any, cast

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


@dataclass(frozen=True)
class ProviderQuery:
    """The exact city/time/category slice needed to evaluate an Intent."""

    city_slug: str
    starts_at: datetime
    ends_at: datetime
    categories: tuple[str, ...] = ()

    def cache_key(self) -> str:
        categories = ",".join(sorted(self.categories))
        category_hash = sha256(categories.encode()).hexdigest()[:12]
        return (
            f"kudago:events:{self.city_slug}:{int(self.starts_at.timestamp())}-"
            f"{int(self.ends_at.timestamp())}:{category_hash}"
        )


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

    def __init__(self, client: redis.Redis | None = None) -> None:
        self.client = client or redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def get_events(self, query: ProviderQuery) -> list[NormalizedLeisureItem] | None:
        try:
            payload = cast(str | None, self.client.get(query.cache_key()))
        except redis.RedisError:
            return None
        if payload is None:
            return None
        try:
            return [NormalizedLeisureItem.from_cache(item) for item in json.loads(payload)]
        except (TypeError, ValueError, KeyError):
            return None

    def set_events(self, query: ProviderQuery, items: list[NormalizedLeisureItem]) -> None:
        try:
            self.client.setex(
                query.cache_key(),
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

    def items(self, query: ProviderQuery) -> list[NormalizedLeisureItem]:
        fetched_at = utcnow()
        params: dict[str, str | int] = {
            "location": query.city_slug,
            "actual_since": int(query.starts_at.timestamp()),
            "actual_until": int(query.ends_at.timestamp()),
            "page_size": 100,
            "fields": "id,title,dates,place,categories,price,is_free,site_url,images",
        }
        if query.categories:
            params["categories"] = ",".join(sorted(query.categories))
        response = httpx.get(
            f"{settings.kudago_base_url}/events/",
            params=params,
            timeout=settings.kudago_timeout_seconds,
        )
        response.raise_for_status()
        return [
            item
            for raw in response.json().get("results", [])
            if (item := normalize_event(raw, query.city_slug, fetched_at)) is not None
        ]


def fetch_items(
    query: ProviderQuery,
    *,
    provider: KudaGoProvider | None = None,
    cache: RedisProviderCache | None = None,
) -> ProviderResult:
    """Cache-aside for one needed provider query; never mirror a whole catalogue."""
    cache = cache or RedisProviderCache()
    cached = cache.get_events(query)
    if cached is not None:
        return ProviderResult(cached, cached=True, fetched_at=cached[0].source_fetched_at if cached else None)
    try:
        items = (provider or KudaGoProvider()).items(query)
    except (httpx.HTTPError, ValueError):
        # A second read lets a value written by another request win a race with failure.
        cached = cache.get_events(query)
        if cached is not None:
            return ProviderResult(cached, cached=True, fetched_at=cached[0].source_fetched_at if cached else None)
        return ProviderResult([], cached=False, fetched_at=None, unavailable=True)
    cache.set_events(query, items)
    return ProviderResult(items, cached=False, fetched_at=items[0].source_fetched_at if items else utcnow())
