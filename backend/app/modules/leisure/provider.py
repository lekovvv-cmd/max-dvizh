"""KudaGo adapter with a Redis-only external catalogue cache.

Provider records are deliberately plain normalized DTOs. They never become
PostgreSQL rows unless matching creates a CandidatePlan, at which point the
plan receives its own immutable source snapshot.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, cast
from urllib.parse import urlparse

import httpx
import redis

from app.core.config import settings
from app.modules.leisure.taxonomy import CONFIDENCE_ORDER, classify, expand, retrieval


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
    categories: tuple[str, ...] = ()
    price_kind: str = "UNKNOWN"
    address_text: str | None = None
    opening_hours_unverified: bool = False
    timetable: str | None = None
    classification_confidence: str = "UNKNOWN"

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
        converted["categories"] = tuple(cast(list[str], converted.get("categories") or []))
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
    product: bool = False

    def cache_key(self) -> str:
        categories = ",".join(sorted(self.categories))
        category_hash = sha256(categories.encode()).hexdigest()[:12]
        return (
            f"kudago:items:{'product' if self.product else 'legacy'}:{self.city_slug}:{int(self.starts_at.timestamp())}-"
            f"{int(self.ends_at.timestamp())}:{category_hash}"
        )


EVENT_CATEGORY_MAP = {
    "quest": ("games", "quest"),
    "entertainment": ("games",),
    "recreation": ("sport",),
    "exhibition": ("exhibition",),
    "theater": ("exhibition", "theater"),
    "tour": ("exhibition", "tour"),
    "concert": ("concert",),
    "party": ("concert", "party"),
}
PLACE_CATEGORY_MAP = {
    "anticafe": ("games", "anticafe"),
    "questroom": ("games", "quest"),
    "amusement": ("games", "sport"),
    "clubs": ("games", "concert", "party"),
    "recreation": ("sport",),
    "stable": ("sport", "stable"),
    "museums": ("exhibition", "museum"),
    "art-centers": ("exhibition",),
    "art-space": ("exhibition",),
    "theatre": ("exhibition", "theater"),
    "concert-hall": ("concert",),
}
WELLNESS_PLACE_CATEGORIES = {"salons", "suburb", "recreation", "amusement"}
WELLNESS_WORDS = re.compile(
    r"бан[яиеюьн]|саун|(?<![а-яёa-z])(?:спа|spa)(?![а-яёa-z])|терм[ыа]|парн[аяоы]", re.I
)


def mapped_categories(
    raw: list[str], category_map: Mapping[str, tuple[str, ...]]
) -> tuple[str, ...]:
    return tuple(sorted({internal for slug in raw for internal in category_map.get(slug, ())}))


def price_kind(value: str | None, is_free: bool) -> tuple[str, int | None]:
    if is_free:
        return "FREE", 0
    if not value:
        return "UNKNOWN", None
    numbers = re.findall(r"(?<!\d)(\d{1,6})(?!\d)", value.replace(" ", ""))
    if value.lower().lstrip().startswith("от ") and numbers:
        return "FROM", int(numbers[0])
    if len(numbers) == 1 and re.fullmatch(
        r"\s*\d[\d\s]*\s*(?:₽|руб(?:лей|ля|ль|\.)?)\s*", value, re.I
    ):
        return "EXACT", int(numbers[0])
    return "UNKNOWN", None


def parse_price(value: str | None, is_free: bool) -> int | None:
    return price_kind(value, is_free)[1]


def normalize_event(
    raw: dict[str, Any], city: str, fetched_at: datetime
) -> NormalizedLeisureItem | None:
    items = normalize_events(raw, city, fetched_at)
    return items[0] if items else None


def normalize_events(
    raw: dict[str, Any], city: str, fetched_at: datetime
) -> list[NormalizedLeisureItem]:
    dates = raw.get("dates") or []
    if not raw.get("id"):
        return []
    place = raw.get("place") or {}
    coords = place.get("coords") or raw.get("coords") or {}
    categories = raw.get("categories") or []
    normalized = mapped_categories(categories, EVENT_CATEGORY_MAP)
    price_text = raw.get("price") or None
    free = bool(raw.get("is_free", False))
    kind, minimum = price_kind(price_text, free)
    items: list[NormalizedLeisureItem] = []
    for date in dates:
        try:
            start_timestamp = int(date["start"])
            end_timestamp = int(date["end"])
            if start_timestamp <= 0 or end_timestamp <= start_timestamp:
                continue
            start = datetime.fromtimestamp(start_timestamp, UTC)
            end = datetime.fromtimestamp(end_timestamp, UTC)
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            # An event without a documented end cannot make a verified Offer.
            continue
        items.append(
            NormalizedLeisureItem(
                provider="KUDAGO",
                provider_id=str(raw["id"]),
                item_type="EVENT",
                city_slug=city,
                title=str(raw.get("title") or "Событие KudaGo"),
                category=normalized[0] if normalized else "other",
                venue_name=place.get("title"),
                latitude=coords.get("lat"),
                longitude=coords.get("lon"),
                starts_at=start,
                ends_at=end,
                price_text=price_text,
                price_min=minimum,
                source_url=raw.get("site_url"),
                image_url=((raw.get("images") or [{}])[0] or {}).get("image"),
                source_fetched_at=fetched_at,
                categories=normalized,
                price_kind=kind,
            )
        )
    return items


def normalize_place(
    raw: dict[str, Any], query: ProviderQuery, fetched_at: datetime
) -> NormalizedLeisureItem | None:
    if not raw.get("id") or raw.get("is_closed") is True or not raw.get("site_url"):
        return None
    raw_categories = raw.get("categories") or []
    categories = mapped_categories(raw_categories, PLACE_CATEGORY_MAP)
    if WELLNESS_PLACE_CATEGORIES.intersection(raw_categories) and WELLNESS_WORDS.search(
        f"{raw.get('title') or ''} {raw.get('description') or ''}"
    ):
        categories = tuple(sorted({*categories, "wellness"}))
    coords = raw.get("coords") or {}
    return NormalizedLeisureItem(
        provider="KUDAGO",
        provider_id=str(raw["id"]),
        item_type="PLACE",
        city_slug=query.city_slug,
        title=str(raw.get("title") or "Место KudaGo"),
        category=categories[0] if categories else "other",
        categories=categories,
        venue_name=str(raw.get("title") or ""),
        starts_at=query.starts_at,
        ends_at=query.ends_at,
        latitude=coords.get("lat"),
        longitude=coords.get("lon"),
        price_text=None,
        price_min=None,
        source_url=raw.get("site_url"),
        image_url=((raw.get("images") or [{}])[0] or {}).get("image"),
        source_fetched_at=fetched_at,
        price_kind="UNKNOWN",
        address_text=raw.get("address"),
        opening_hours_unverified=True,
        timetable=raw.get("timetable"),
    )


class RedisProviderCache:
    """Small cache module, intentionally not a separate infrastructure layer."""

    def __init__(self, client: redis.Redis | None = None) -> None:
        self.client = client or (
            redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.5,
            )
            if settings.redis_url
            else None
        )

    def get_events(self, query: ProviderQuery) -> list[NormalizedLeisureItem] | None:
        if self.client is None:
            return None
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
        if self.client is None:
            return
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
    def item_available(
        self, item_type: str, provider_id: str, starts_at: datetime, ends_at: datetime
    ) -> bool | None:
        """Check a saved source slot; None means the provider could not verify it."""
        if not provider_id.isdecimal() or item_type not in {"EVENT", "PLACE"}:
            return None
        kind = "events" if item_type == "EVENT" else "places"
        fields = "id,dates" if item_type == "EVENT" else "id,is_closed"
        try:
            response = httpx.get(
                f"{settings.kudago_base_url}/{kind}/{provider_id}/",
                params={"fields": fields},
                timeout=settings.kudago_timeout_seconds,
            )
            if response.status_code == 404:
                return False
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(data, dict) or str(data.get("id")) != provider_id:
            return None
        if item_type == "PLACE":
            closed = data.get("is_closed")
            return not closed if isinstance(closed, bool) else None
        dates = data.get("dates")
        if not isinstance(dates, list):
            return None
        selected = (int(starts_at.timestamp()), int(ends_at.timestamp()))
        for date in dates:
            if isinstance(date, dict):
                try:
                    if (int(date["start"]), int(date["end"])) == selected:
                        return True
                except (KeyError, TypeError, ValueError):
                    continue
        return False

    def cities(self) -> list[dict[str, str]]:
        response = httpx.get(
            f"{settings.kudago_base_url}/locations/",
            params={"lang": "ru", "fields": "slug,name,timezone"},
            timeout=settings.kudago_timeout_seconds,
        )
        response.raise_for_status()
        return [
            {
                "slug": str(city["slug"]),
                "name": str(city["name"]),
                "timezone": str(city.get("timezone") or "UTC"),
            }
            for city in response.json()
            if city.get("slug") != "interesting" and city.get("slug") and city.get("name")
        ]

    def items(self, query: ProviderQuery) -> list[NormalizedLeisureItem]:
        if query.product:
            return self.product_items(query)
        fetched_at = utcnow()
        result: list[NormalizedLeisureItem] = []
        event_filters = {
            "games": "quest,entertainment",
            "quest": "quest",
            "sport": "recreation",
            "exhibition": "exhibition,theater,tour",
            "theater": "theater",
            "tour": "tour",
            "concert": "concert,party",
            "party": "party",
        }
        place_filters = {
            "games": "anticafe,questroom,amusement,clubs",
            "quest": "questroom",
            "anticafe": "anticafe",
            "sport": "recreation,amusement,stable",
            "stable": "stable",
            "exhibition": "museums,art-centers,art-space,theatre",
            "museum": "museums",
            "theater": "theatre",
            "concert": "concert-hall,clubs",
            "party": "clubs",
            "wellness": "salons,suburb,recreation,amusement",
        }
        for kind in ("events", "places"):
            filters = event_filters if kind == "events" else place_filters
            if query.categories and all(category not in filters for category in query.categories):
                continue
            params: dict[str, str | int] = {"location": query.city_slug, "page_size": 100}
            if kind == "events":
                params.update(
                    {
                        "actual_since": int(query.starts_at.timestamp()),
                        "actual_until": int(query.ends_at.timestamp()),
                        "fields": "id,title,dates,place,categories,price,is_free,site_url,images",
                        "expand": "place",
                    }
                )
                selected = sorted(
                    {
                        slug
                        for category in query.categories
                        for slug in event_filters.get(category, "").split(",")
                        if slug
                    }
                )
            else:
                params["fields"] = (
                    "id,title,description,address,location,site_url,is_closed,coords,categories,timetable,images"
                )
                selected = sorted(
                    {
                        slug
                        for category in query.categories
                        for slug in place_filters.get(category, "").split(",")
                        if slug
                    }
                )
            if selected:
                params["categories"] = ",".join(selected)
            for page in range(1, max(1, settings.kudago_max_pages) + 1):
                params["page"] = page
                response = httpx.get(
                    f"{settings.kudago_base_url}/{kind}/",
                    params=params,
                    timeout=settings.kudago_timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                for raw in data.get("results", []):
                    if kind == "events":
                        result.extend(normalize_events(raw, query.city_slug, fetched_at))
                    else:
                        place = normalize_place(raw, query, fetched_at)
                        if place is not None:
                            result.append(place)
                if not data.get("next"):
                    break
        return result

    def product_items(self, query: ProviderQuery) -> list[NormalizedLeisureItem]:
        """Bounded native-category and documented full-text retrieval, then strict classification."""
        place_categories, event_categories, searches = retrieval(query.categories)
        selected = expand(query.categories)
        fetched_at = utcnow()
        raw_items: list[tuple[str, dict[str, Any]]] = []
        last_error: httpx.HTTPError | ValueError | None = None
        fields_place = "id,title,description,address,location,site_url,is_closed,coords,categories,tags,timetable,images"
        fields_event = (
            "id,title,description,dates,place,categories,tags,price,is_free,site_url,images"
        )
        for kind, categories in (("places", place_categories), ("events", event_categories)):
            if not categories:
                continue
            params: dict[str, str | int] = {
                "location": query.city_slug,
                "categories": ",".join(sorted(categories)),
                "fields": fields_place if kind == "places" else fields_event,
                "page_size": 100,
                "text_format": "plain",
            }
            if kind == "events":
                params.update(
                    {
                        "actual_since": int(query.starts_at.timestamp()),
                        "actual_until": int(query.ends_at.timestamp()),
                        "expand": "place",
                    }
                )
            for page in range(1, max(1, settings.kudago_max_pages) + 1):
                params["page"] = page
                try:
                    response = httpx.get(
                        f"{settings.kudago_base_url}/{kind}/",
                        params=params,
                        timeout=settings.kudago_timeout_seconds,
                    )
                    response.raise_for_status()
                    data = response.json()
                except (httpx.HTTPError, ValueError) as error:
                    last_error = error
                    break
                raw_items.extend((kind, raw) for raw in data.get("results", []))
                if not data.get("next"):
                    break
        seen_search_ids: set[str] = set()
        for search in sorted(searches):
            try:
                response = httpx.get(
                    f"{settings.kudago_base_url}/search/",
                    params={"q": search, "location": query.city_slug, "ctype": "place"},
                    timeout=settings.kudago_timeout_seconds,
                )
                response.raise_for_status()
                hits = response.json().get("results", [])
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                continue
            for hit in hits[:8]:
                identifier = str(hit.get("id") or "")
                if not identifier.isdecimal():
                    continue
                seen_search_ids.add(identifier)
        if seen_search_ids:
            try:
                response = httpx.get(
                    f"{settings.kudago_base_url}/places/",
                    params={
                        "ids": ",".join(sorted(seen_search_ids)[:40]),
                        "fields": fields_place,
                        "page_size": 40,
                        "text_format": "plain",
                    },
                    timeout=settings.kudago_timeout_seconds,
                )
                response.raise_for_status()
                raw_items.extend(("places", raw) for raw in response.json().get("results", []))
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
        result: list[NormalizedLeisureItem] = []
        seen: set[tuple[str, str, datetime]] = set()
        for kind, raw in raw_items:
            item_type = "PLACE" if kind == "places" else "EVENT"
            confidence = classify(raw, item_type)
            activity_ids = tuple(
                sorted(
                    aid
                    for aid in selected
                    if CONFIDENCE_ORDER.get(confidence.get(aid, "UNKNOWN"), 0) >= 2
                )
            )
            if not activity_ids:
                continue
            normalized = (
                ([place] if (place := normalize_place(raw, query, fetched_at)) else [])
                if kind == "places"
                else normalize_events(raw, query.city_slug, fetched_at)
            )
            for item in normalized:
                key = (item.item_type, item.provider_id, item.starts_at)
                if key in seen:
                    continue
                seen.add(key)
                result.append(
                    replace(
                        item,
                        categories=activity_ids,
                        category=activity_ids[0],
                        classification_confidence=max(
                            (confidence[aid] for aid in activity_ids),
                            key=lambda value: CONFIDENCE_ORDER[value],
                        ),
                    )
                )
        if not result and last_error is not None:
            raise last_error
        return result

    def search_place_items(self, query: ProviderQuery, phrase: str) -> list[NormalizedLeisureItem]:
        """Manual name search; results still pass the same deterministic classifier."""
        fields = "id,title,description,address,location,site_url,is_closed,coords,categories,tags,timetable,images"
        parsed = urlparse(phrase)
        if parsed.scheme or parsed.netloc:
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or not (parsed.hostname == "kudago.com" or parsed.hostname.endswith(".kudago.com"))
            ):
                return []
            match = re.fullmatch(r"/place/[^/]*-(\d+)/?", parsed.path) or re.fullmatch(
                r"/public-api/v[\d.]+/places/(\d+)/?", parsed.path
            )
            if match is None:
                return []
            response = httpx.get(
                f"{settings.kudago_base_url}/places/{match.group(1)}/",
                params={"fields": fields, "text_format": "plain"},
                timeout=settings.kudago_timeout_seconds,
            )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            places = [response.json()]
        else:
            search = httpx.get(
                f"{settings.kudago_base_url}/search/",
                params={"q": phrase, "location": query.city_slug, "ctype": "place"},
                timeout=settings.kudago_timeout_seconds,
            )
            search.raise_for_status()
            identifiers = sorted(
                {
                    str(hit.get("id"))
                    for hit in search.json().get("results", [])[:20]
                    if str(hit.get("id") or "").isdecimal()
                }
            )
            if not identifiers:
                return []
            response = httpx.get(
                f"{settings.kudago_base_url}/places/",
                params={
                    "ids": ",".join(identifiers),
                    "fields": fields,
                    "page_size": 20,
                    "text_format": "plain",
                },
                timeout=settings.kudago_timeout_seconds,
            )
            response.raise_for_status()
            places = response.json().get("results", [])
        selected = expand(query.categories)
        fetched_at = utcnow()
        result: list[NormalizedLeisureItem] = []
        for raw in places:
            if raw.get("location") != query.city_slug:
                continue
            confidence = classify(raw, "PLACE")
            activities = tuple(
                sorted(
                    aid
                    for aid in selected
                    if CONFIDENCE_ORDER.get(confidence.get(aid, "UNKNOWN"), 0) >= 2
                )
            )
            place = normalize_place(raw, query, fetched_at)
            if place and activities:
                result.append(
                    replace(
                        place,
                        categories=activities,
                        category=activities[0],
                        classification_confidence=max(
                            (confidence[aid] for aid in activities),
                            key=lambda value: CONFIDENCE_ORDER[value],
                        ),
                    )
                )
        return result


def fetch_items(
    query: ProviderQuery,
    *,
    provider: KudaGoProvider | None = None,
    cache: RedisProviderCache | None = None,
    force_refresh: bool = False,
) -> ProviderResult:
    """Cache-aside for one needed provider query; never mirror a whole catalogue."""
    cache = cache or RedisProviderCache()
    cached = None if force_refresh else cache.get_events(query)
    if cached is not None:
        return ProviderResult(
            cached, cached=True, fetched_at=cached[0].source_fetched_at if cached else None
        )
    try:
        items = (provider or KudaGoProvider()).items(query)
    except (httpx.HTTPError, ValueError):
        # A second read lets a value written by another request win a race with failure.
        cached = cache.get_events(query)
        if cached is not None:
            return ProviderResult(
                cached, cached=True, fetched_at=cached[0].source_fetched_at if cached else None
            )
        return ProviderResult([], cached=False, fetched_at=None, unavailable=True)
    cache.set_events(query, items)
    return ProviderResult(
        items, cached=False, fetched_at=items[0].source_fetched_at if items else utcnow()
    )
