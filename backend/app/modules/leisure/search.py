"""Bounded, structured retrieval for the Dvizh candidate flow."""

from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.modules.leisure.provider import (
    KudaGoProvider,
    NormalizedLeisureItem,
    ProviderQuery,
    ProviderResult,
)
from app.modules.leisure.taxonomy import (
    expand,
    geoapify_categories_for_activity,
    geoapify_retrieval,
    retrieval,
)
from app.modules.matching.domain import haversine_km

logger = logging.getLogger(__name__)
CITY_NAMES = {
    "msk": "Москва",
    "spb": "Санкт-Петербург",
    "ekb": "Екатеринбург",
    "kzn": "Казань",
    "nn": "Нижний Новгород",
    "nnv": "Нижний Новгород",
    "nsk": "Новосибирск",
}
_city_ids: dict[str, tuple[str, float]] = {}
_kudago_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="kudago-search")


class VenueProvider(Protocol):
    async def search_places(
        self, query: ProviderQuery, client: httpx.AsyncClient, *, offset: int = 0
    ) -> list[NormalizedLeisureItem]: ...


def _category_matches(actual: str, requested: str) -> bool:
    return actual == requested or actual.startswith(requested + ".")


def _activity_ids(properties: dict[str, Any], selected: set[str]) -> tuple[str, ...]:
    categories = tuple(str(value) for value in properties.get("categories") or ())
    title = str(properties.get("name") or "").casefold()
    matches: list[str] = []
    for activity in sorted(selected):
        provider_categories = geoapify_categories_for_activity(activity)
        if any(
            _category_matches(actual, requested)
            for actual in categories
            for requested in provider_categories
        ):
            matches.append(activity)
        elif activity == "billiards" and ("бильярд" in title or "billiard" in title):
            matches.append(activity)
    return tuple(matches)


def _normalize(
    feature: dict[str, Any], query: ProviderQuery, fetched_at: datetime
) -> NormalizedLeisureItem | None:
    properties = feature.get("properties") or {}
    if not isinstance(properties, dict):
        return None
    title = str(properties.get("name") or "").strip()
    identifier = str(properties.get("place_id") or "")
    activities = _activity_ids(properties, expand(query.categories))
    if not title or not identifier or not activities:
        return None
    coordinates = (feature.get("geometry") or {}).get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        return None
    try:
        longitude, latitude = float(coordinates[0]), float(coordinates[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    if query.origin_kind == "USER_POINT" and query.radius_m is not None:
        if query.latitude is None or query.longitude is None:
            return None
        if (
            haversine_km(query.latitude, query.longitude, latitude, longitude) * 1000
            > query.radius_m
        ):
            return None
    website = properties.get("website")
    source_url = (
        website if isinstance(website, str) and urlparse(website).scheme == "https" else None
    )
    address = properties.get("formatted")
    return NormalizedLeisureItem(
        provider="GEOAPIFY",
        provider_id=sha256(identifier.encode()).hexdigest()[:32],
        item_type="PLACE",
        city_slug=query.city_slug,
        title=title,
        category=activities[0],
        categories=activities,
        classification_confidence="HIGH",
        venue_name=title,
        starts_at=query.starts_at,
        ends_at=query.ends_at,
        latitude=latitude,
        longitude=longitude,
        price_text=None,
        price_min=None,
        price_kind="UNKNOWN",
        source_url=source_url,
        image_url=None,
        address_text=str(address) if address else None,
        opening_hours_unverified=True,
        source_fetched_at=fetched_at,
    )


class GeoapifyVenueProvider:
    async def _city_id(self, city_slug: str, client: httpx.AsyncClient) -> str:
        cached = _city_ids.get(city_slug)
        if cached and cached[1] > monotonic():
            return cached[0]
        city = CITY_NAMES.get(city_slug, city_slug.replace("-", " "))
        response = await client.get(
            "/v1/geocode/search",
            params={
                "text": f"{city}, Россия",
                "type": "city",
                "format": "json",
                "limit": 1,
                "apiKey": settings.geoapify_api_key,
            },
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            raise ValueError("Geoapify city boundary unavailable")
        result = results[0]
        if str(result.get("country_code") or "").casefold() != "ru":
            raise ValueError("Geoapify city boundary mismatch")
        identifier = str(result.get("place_id") or "")
        if not identifier:
            raise ValueError("Geoapify city boundary missing place_id")
        _city_ids[city_slug] = (identifier, monotonic() + 86400)
        return identifier

    async def search_places(
        self, query: ProviderQuery, client: httpx.AsyncClient, *, offset: int = 0
    ) -> list[NormalizedLeisureItem]:
        categories, name_searches = geoapify_retrieval(query.categories)
        if not categories and not name_searches:
            return []
        if query.origin_kind == "USER_POINT":
            if query.latitude is None or query.longitude is None or query.radius_m is None:
                raise ValueError("USER_POINT requires coordinates and radius")
            geo_filter = f"circle:{query.longitude},{query.latitude},{query.radius_m}"
            bias = f"proximity:{query.longitude},{query.latitude}"
        else:
            geo_filter = f"place:{await self._city_id(query.city_slug, client)}"
            bias = None
        requests: list[dict[str, str | int]] = []
        if categories:
            requests.append({"categories": ",".join(categories)})
        for name in name_searches:
            requests.append({"categories": "entertainment,catering.bar", "name": name})
        fetched_at = datetime.now(UTC)

        async def fetch(extra: dict[str, str | int]) -> list[NormalizedLeisureItem]:
            params: dict[str, str | int] = {
                **extra,
                "filter": geo_filter,
                "limit": min(query.limit, 40),
                "offset": offset,
                "lang": "ru",
                "apiKey": settings.geoapify_api_key,
            }
            if bias:
                params["bias"] = bias
            response = await client.get("/v2/places", params=params)
            response.raise_for_status()
            return [
                item
                for feature in response.json().get("features", [])
                if isinstance(feature, dict)
                if (item := _normalize(feature, query, fetched_at)) is not None
            ]

        batches = await asyncio.gather(*(fetch(request) for request in requests))
        return [item for batch in batches for item in batch]


def _identity(item: NormalizedLeisureItem) -> str:
    return re.sub(r"\W+", "", item.title.casefold())


def dedupe(items: list[NormalizedLeisureItem]) -> list[NormalizedLeisureItem]:
    result: list[NormalizedLeisureItem] = []
    for item in items:
        duplicate_at = next(
            (
                index
                for index, previous in enumerate(result)
                if item.item_type == previous.item_type
                and _identity(item) == _identity(previous)
                and (
                    item.latitude is not None
                    and item.longitude is not None
                    and previous.latitude is not None
                    and previous.longitude is not None
                    and haversine_km(
                        item.latitude, item.longitude, previous.latitude, previous.longitude
                    )
                    < 0.15
                    or bool(
                        item.address_text
                        and previous.address_text
                        and item.address_text.casefold() == previous.address_text.casefold()
                    )
                )
                and (item.item_type != "EVENT" or item.starts_at == previous.starts_at)
            ),
            None,
        )
        if duplicate_at is None:
            result.append(item)
        else:
            previous = result[duplicate_at]
            result[duplicate_at] = replace(
                previous,
                price_text=previous.price_text or item.price_text,
                price_min=previous.price_min if previous.price_min is not None else item.price_min,
                source_url=previous.source_url or item.source_url,
                image_url=previous.image_url or item.image_url,
                address_text=previous.address_text or item.address_text,
                categories=tuple(sorted(set(previous.categories) | set(item.categories))),
            )
    return result


async def _search(query: ProviderQuery) -> ProviderResult:
    started = monotonic()
    geo_categories, geo_names = geoapify_retrieval(query.categories)
    place_categories, event_categories, searches = retrieval(query.categories)
    needs_geo = bool(geo_categories or geo_names)
    needs_kudago = bool(place_categories or event_categories or searches)
    tasks: dict[str, asyncio.Task[list[NormalizedLeisureItem]]] = {}
    counts = {"geoapify": 0, "kudago": 0}
    timings = {"geoapify": 0, "kudago": 0}
    failed: set[str] = set()
    async with httpx.AsyncClient(
        base_url=settings.geoapify_base_url.rstrip("/"),
        timeout=settings.geoapify_timeout_seconds,
    ) as client:

        async def geo() -> list[NormalizedLeisureItem]:
            began = monotonic()
            try:
                return await GeoapifyVenueProvider().search_places(query, client)
            finally:
                timings["geoapify"] = round((monotonic() - began) * 1000)

        async def kudago() -> list[NormalizedLeisureItem]:
            began = monotonic()
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    _kudago_pool, KudaGoProvider().product_items, query
                )
            finally:
                timings["kudago"] = round((monotonic() - began) * 1000)

        if needs_geo:
            if settings.geoapify_api_key:
                tasks["geoapify"] = asyncio.create_task(geo())
            else:
                failed.add("geoapify")
        if needs_kudago:
            tasks["kudago"] = asyncio.create_task(kudago())
        done, pending = (
            await asyncio.wait(tasks.values(), timeout=settings.leisure_search_deadline_seconds)
            if tasks
            else (set(), set())
        )
        for task in pending:
            task.cancel()
        items: list[NormalizedLeisureItem] = []
        for name, task in tasks.items():
            if task not in done:
                failed.add(name)
                continue
            try:
                batch = task.result()
                counts[name] = len(batch)
                items.extend(batch)
            except (httpx.HTTPError, ValueError):
                failed.add(name)
        normalized_count = len(items)
        dedupe_started = monotonic()
        items = dedupe(items)
        dedupe_ms = round((monotonic() - dedupe_started) * 1000)
        # A single bounded second pass improves sparse venue searches without
        # broadening the user's activities or radius.
        if len(items) < 8 and needs_geo and "geoapify" not in failed:
            try:
                more = await asyncio.wait_for(
                    GeoapifyVenueProvider().search_places(
                        query, client, offset=min(query.limit, 40)
                    ),
                    timeout=max(
                        0.1, settings.leisure_search_deadline_seconds - (monotonic() - started)
                    ),
                )
                counts["geoapify"] += len(more)
                normalized_count += len(more)
                dedupe_started = monotonic()
                items = dedupe([*items, *more])
                dedupe_ms += round((monotonic() - dedupe_started) * 1000)
            except (httpx.HTTPError, ValueError, TimeoutError):
                failed.add("geoapify")
    primary_failed = (needs_geo and "geoapify" in failed) or (
        bool(event_categories) and "kudago" in failed
    )
    unavailable = not items and (primary_failed or (needs_kudago and "kudago" in failed))
    logger.info(
        "leisure_search city=%s origin=%s activities=%s providers=%s kudago_count=%d geoapify_count=%d normalized_count=%d deduped_count=%d pool_count=%d kudago_ms=%d geoapify_ms=%d dedupe_ms=%d total_ms=%d partial=%s",
        query.city_slug,
        "user" if query.origin_kind == "USER_POINT" else "city",
        ",".join(sorted(query.categories)),
        ",".join(tasks),
        counts["kudago"],
        counts["geoapify"],
        normalized_count,
        len(items),
        len(items),
        timings["kudago"],
        timings["geoapify"],
        dedupe_ms,
        round((monotonic() - started) * 1000),
        bool(failed),
    )
    return ProviderResult(
        items,
        cached=False,
        fetched_at=datetime.now(UTC),
        unavailable=unavailable,
        partial=bool(failed),
    )


def search_product(query: ProviderQuery) -> ProviderResult:
    return asyncio.run(_search(query))


def search_exact_place(query: ProviderQuery, phrase: str) -> ProviderResult:
    """Run name lookup only after explicit submit, including the KudaGo fallback."""

    async def run() -> ProviderResult:
        items: list[NormalizedLeisureItem] = []
        failed = False
        parsed = urlparse(phrase)
        if not parsed.scheme and settings.geoapify_api_key:
            async with httpx.AsyncClient(
                base_url=settings.geoapify_base_url.rstrip("/"),
                timeout=settings.geoapify_timeout_seconds,
            ) as client:
                try:
                    categories, names = geoapify_retrieval(query.categories)
                    if names:
                        categories = (*categories, "entertainment", "catering.bar")
                    if categories:
                        provider = GeoapifyVenueProvider()
                        boundary = (
                            f"circle:{query.longitude},{query.latitude},{query.radius_m}"
                            if query.origin_kind == "USER_POINT"
                            else f"place:{await provider._city_id(query.city_slug, client)}"
                        )
                        response = await client.get(
                            "/v2/places",
                            params={
                                "categories": ",".join(categories),
                                "filter": boundary,
                                "name": phrase,
                                "limit": 20,
                                "lang": "ru",
                                "apiKey": settings.geoapify_api_key,
                            },
                        )
                        response.raise_for_status()
                        fetched = datetime.now(UTC)
                        items.extend(
                            item
                            for feature in response.json().get("features", [])
                            if isinstance(feature, dict)
                            if (item := _normalize(feature, query, fetched)) is not None
                        )
                except (httpx.HTTPError, ValueError):
                    failed = True
        try:
            items.extend(
                await asyncio.get_running_loop().run_in_executor(
                    _kudago_pool, KudaGoProvider().search_place_items, query, phrase
                )
            )
        except (httpx.HTTPError, ValueError):
            failed = True
        combined = dedupe(items)
        return ProviderResult(
            combined, False, datetime.now(UTC), unavailable=failed and not combined, partial=failed
        )

    return asyncio.run(run())
