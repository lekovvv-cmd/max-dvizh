"""Shared Geoapify city boundaries for search and address suggestions."""

from __future__ import annotations

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


def city_name(city_slug: str) -> str:
    return CITY_NAMES.get(city_slug, city_slug.replace("-", " "))


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
