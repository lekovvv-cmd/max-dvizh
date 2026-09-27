"""Structured Dvizh retrieval and provider degradation regressions."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Any

import httpx

from app.modules.leisure import geoapify, search
from app.modules.leisure.provider import NormalizedLeisureItem, ProviderQuery
from app.modules.leisure.taxonomy import expand, geoapify_retrieval, retrieval_intents


def query(*activities: str, point: bool = False) -> ProviderQuery:
    start = datetime.now(UTC) + timedelta(hours=2)
    return ProviderQuery(
        "spb",
        start,
        start + timedelta(hours=3),
        activities,
        product=True,
        origin_kind="USER_POINT" if point else "CITY_BOUNDARY",
        latitude=59.9343 if point else None,
        longitude=30.3351 if point else None,
        radius_m=3000 if point else None,
    )


def feature(name: str = "Летний сад", longitude: float = 30.3351) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "place_id": f"place-{name}",
            "name": name,
            "categories": ["leisure.park.garden"],
            "formatted": f"Санкт-Петербург, {longitude}",
        },
        "geometry": {"type": "Point", "coordinates": [longitude, 59.9343]},
    }


def test_structured_mapping_and_walk_does_not_become_ropes_course() -> None:
    assert retrieval_intents(["restaurant"]) == ("CAFE_RESTAURANT",)
    assert retrieval_intents(["bowling"]) == ("BOWLING",)
    assert retrieval_intents(["ropes_course"]) == ("ROPES_COURSE",)
    assert retrieval_intents(["walk"]) == ("GARDEN", "PARK", "WALK")
    assert geoapify_retrieval(["restaurant"])[0] == (
        "catering.cafe",
        "catering.restaurant",
    )
    assert geoapify_retrieval(["bowling"])[0] == ("entertainment.bowling_alley",)
    assert geoapify_retrieval(["billiards"])[1] == ("бильярд",)
    assert geoapify_retrieval(["walk"])[0] == ("leisure.park", "leisure.park.garden")
    assert "walk" in expand(["walk/*"])
    assert "bowling" in expand(["games/*"])
    assert "ropes_course" not in search._activity_ids(
        feature()["properties"], {"walk", "ropes_course"}
    )


def test_geoapify_uses_city_boundary_without_coordinates_and_circle_with_point(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(search, "settings", replace(search.settings, geoapify_api_key="test"))
    monkeypatch.setattr(geoapify, "settings", search.settings)
    geoapify._cities.clear()
    seen: list[tuple[str, dict[str, str]]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append((request.url.path, params))
        if request.url.path.endswith("/geocode/search"):
            return httpx.Response(
                200, json={"results": [{"place_id": "city-id", "country_code": "ru"}]}
            )
        return httpx.Response(200, json={"features": [feature()]})

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="https://api.geoapify.com", transport=httpx.MockTransport(respond)
        ) as client:
            provider = search.GeoapifyVenueProvider()
            city_items = await provider.search_places(query("walk"), client)
            near_items = await provider.search_places(query("walk", point=True), client)
        assert len(city_items) == len(near_items) == 1

    asyncio.run(run())
    assert seen[1][1]["filter"] == "place:city-id"
    assert "bias" not in seen[1][1]
    assert seen[2][1]["filter"] == "circle:30.3351,59.9343,3000"
    assert seen[2][1]["bias"] == "proximity:30.3351,59.9343"
    assert all("lat" not in params and "lon" not in params for _, params in seen[:2])


def test_geoapify_rechecks_hard_radius_server_side() -> None:
    inside = search._normalize(feature(), query("walk", point=True), datetime.now(UTC))
    outside = search._normalize(
        feature(longitude=30.5), query("walk", point=True), datetime.now(UTC)
    )
    assert inside is not None and outside is None


def _item(provider: str, name: str, lon: float) -> NormalizedLeisureItem:
    request = query("walk")
    item = search._normalize(feature(name, lon), request, datetime.now(UTC))
    assert item is not None
    return replace(
        item,
        provider=provider,
        provider_id=f"{provider}-{name}-{lon}",
    )


def test_cross_provider_dedupe_preserves_distinct_branches() -> None:
    first = _item("GEOAPIFY", "Surf Coffee", 30.3351)
    same = _item("KUDAGO", "Surf Coffee", 30.3355)
    branch = _item("GEOAPIFY", "Surf Coffee", 30.5)
    assert len(search.dedupe([first, same, branch])) == 2


def test_provider_tasks_start_concurrently_and_keep_partial_result(monkeypatch: Any) -> None:
    monkeypatch.setattr(search, "settings", replace(search.settings, geoapify_api_key="test"))
    started = Event()

    async def geo(
        self: search.GeoapifyVenueProvider,
        requested: ProviderQuery,
        client: httpx.AsyncClient,
        *,
        offset: int = 0,
    ) -> list[NormalizedLeisureItem]:
        assert await asyncio.to_thread(started.wait, 1)
        return [_item("GEOAPIFY", "Кафе", 30.3351)]

    def kudago(self: Any, requested: ProviderQuery) -> list[NormalizedLeisureItem]:
        started.set()
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(search.GeoapifyVenueProvider, "search_places", geo)
    monkeypatch.setattr(search.KudaGoProvider, "product_items", kudago)
    result = search.search_product(query("restaurant"))
    assert len(result.items) == 1
    assert result.partial and not result.unavailable


def test_missing_primary_venue_key_is_not_no_source(monkeypatch: Any) -> None:
    monkeypatch.setattr(search, "settings", replace(search.settings, geoapify_api_key=""))
    monkeypatch.setattr(search.KudaGoProvider, "product_items", lambda self, requested: [])
    result = search.search_product(query("restaurant"))
    assert not result.items and result.unavailable and result.partial


def test_kudago_nearby_query_passes_explicit_radius_to_provider(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []

    def get(url: str, *, params: dict[str, Any], timeout: float) -> httpx.Response:
        calls.append(dict(params))
        return httpx.Response(200, json={"results": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(search.httpx, "get", get)
    search.KudaGoProvider().product_items(query("concert", point=True))
    assert calls
    assert all(call["lat"] == "59.9343" and call["lon"] == "30.3351" for call in calls)
    assert all(call["radius"] == 3000 for call in calls)


def test_exact_place_search_uses_geoapify_after_explicit_submit(monkeypatch: Any) -> None:
    monkeypatch.setattr(search, "settings", replace(search.settings, geoapify_api_key="test"))
    geoapify._cities["spb"] = ("city-id", "Санкт-Петербург", geoapify.monotonic() + 100)
    real_client = httpx.AsyncClient

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["name"] == "Летний сад"
        return httpx.Response(200, json={"features": [feature()]})

    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(
        search.KudaGoProvider, "search_place_items", lambda self, request, phrase: []
    )
    result = search.search_exact_place(query("walk"), "Летний сад")
    assert [item.provider for item in result.items] == ["GEOAPIFY"]
