"""Shared Geoapify city boundaries for search and address suggestions."""

from __future__ import annotations

import hmac
from hashlib import sha256
from math import isfinite
from time import monotonic

import httpx

from app.core.config import settings

CITY_NAMES = {
    "msk": "Москва",
    "spb": "Санкт-Петербург",
    "ekb": "Екатеринбург",
    "kzn": "Казань",
    "nn": "Нижний Новгород",
    "nnv": "Нижний Новгород",
    "nsk": "Новосибирск",
}
_cities: dict[str, tuple[str, str, float]] = {}
_city_centers: dict[str, tuple[str, float, float, float]] = {}


def place_map_url(latitude: float, longitude: float) -> str | None:
    """Create a signed local URL so the Geoapify key stays on the server."""
    if (
        not settings.geoapify_api_key
        or not isfinite(latitude)
        or not isfinite(longitude)
        or not (-90 <= latitude <= 90 and -180 <= longitude <= 180)
    ):
        return None
    coordinates = f"{latitude:.6f},{longitude:.6f}"
    signature = hmac.new(
        settings.geoapify_api_key.encode(), coordinates.encode(), sha256
    ).hexdigest()[:32]
    return f"/api/v1/place-map/{latitude:.6f}/{longitude:.6f}/{signature}"


def valid_place_map_signature(latitude: float, longitude: float, signature: str) -> bool:
    expected = place_map_url(latitude, longitude)
    return expected is not None and hmac.compare_digest(expected.rsplit("/", 1)[-1], signature)


def city_name(city_slug: str) -> str:
    return CITY_NAMES.get(city_slug, city_slug.replace("-", " "))


async def resolve_city_center(
    city_slug: str, client: httpx.AsyncClient
) -> tuple[str, float, float] | None:
    """Find a city center for autocomplete ranking without requiring its boundary."""
    cached = _city_centers.get(city_slug)
    if cached and cached[3] > monotonic():
        return cached[:3]
    try:
        response = await client.get(
            "/v1/geocode/search",
            params={
                "text": f"{city_name(city_slug)}, Россия",
                "type": "city",
                "format": "json",
                "lang": "ru",
                "limit": 1,
                "apiKey": settings.geoapify_api_key,
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        return None
    result = results[0]
    latitude, longitude = result.get("lat"), result.get("lon")
    if (
        str(result.get("country_code") or "").casefold() != "ru"
        or isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, int | float)
        or not isinstance(longitude, int | float)
        or not isfinite(latitude)
        or not isfinite(longitude)
        or not (-90 <= latitude <= 90 and -180 <= longitude <= 180)
    ):
        return None
    name = str(result.get("city") or result.get("name") or city_name(city_slug)).strip()
    center = (name, float(latitude), float(longitude))
    _city_centers[city_slug] = (*center, monotonic() + 86400)
    return center


async def resolve_city(city_slug: str, client: httpx.AsyncClient) -> tuple[str, str]:
    cached = _cities.get(city_slug)
    if cached and cached[2] > monotonic():
        return cached[0], cached[1]
    response = await client.get(
        "/v1/geocode/search",
        params={
            "text": f"{city_name(city_slug)}, Россия",
            "type": "city",
            "format": "json",
            "lang": "ru",
            "limit": 1,
            "apiKey": settings.geoapify_api_key,
        },
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise ValueError("Geoapify city boundary unavailable")
    result = results[0]
    if str(result.get("country_code") or "").casefold() != "ru":
        raise ValueError("Geoapify city boundary mismatch")
    identifier = str(result.get("place_id") or "")
    if not identifier:
        raise ValueError("Geoapify city boundary missing place_id")
    name = str(result.get("city") or result.get("name") or city_name(city_slug)).strip()
    _cities[city_slug] = (identifier, name, monotonic() + 86400)
    return identifier, name


async def resolve_city_id(city_slug: str, client: httpx.AsyncClient) -> str:
    identifier, _ = await resolve_city(city_slug, client)
    return identifier
