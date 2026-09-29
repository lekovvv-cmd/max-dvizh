"""Address suggestions prioritize the current city while keeping global matches."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes import product
from app.db.models import Base, Group, GroupMember, User
from app.modules.leisure import geoapify


@pytest.fixture
def member() -> Iterator[tuple[Session, User]]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id="address-user", max_user_id="address-user", display_name="User")
        group = Group(
            id="address-group",
            name="Друзья",
            default_city_slug="ekb",
            created_by=user.id,
            invite_token="address-invite",
        )
        session.add_all([user, group])
        session.flush()
        session.add(GroupMember(group_id=group.id, user_id=user.id))
        session.commit()
        yield session, user
    engine.dispose()


def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    active = replace(product.settings, geoapify_api_key="test-key")
    monkeypatch.setattr(product, "settings", active)
    monkeypatch.setattr(geoapify, "settings", active)
    geoapify._city_centers.clear()


def mock_client(monkeypatch: pytest.MonkeyPatch, respond: Any) -> None:
    real_client = httpx.AsyncClient

    def client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return real_client(*args, transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(product.httpx, "AsyncClient", client)


def address(index: int, *, city: str = "Екатеринбург") -> dict[str, object]:
    return {
        "place_id": f"address-{index}",
        "country_code": "ru",
        "city": city,
        "name": f"Место {index}",
        "address_line2": f"Ленина {index}, {city}",
        "formatted": f"Место {index}, Ленина {index}, {city}",
        "lat": 56.838,
        "lon": 60.58,
    }


def test_current_city_first_other_city_available_and_center_cached(
    monkeypatch: pytest.MonkeyPatch, member: tuple[Session, User]
) -> None:
    configured(monkeypatch)
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/geocode/search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"city": "Екатеринбург", "country_code": "ru", "lat": 56.84, "lon": 60.6}
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    address(0, city="Москва"),
                    {**address(1), "lat": "invalid"},
                    *(address(index) for index in range(2, 9)),
                ]
            },
        )

    mock_client(monkeypatch, respond)
    monkeypatch.setattr(product.KudaGoProvider, "cities", lambda self: pytest.fail("KudaGo called"))
    session, user = member
    first = product.suggest_locations(session, user, q="Ленина 1", city="ekb")
    second = product.suggest_locations(session, user, q="Ленина 2", city="ekb")
    assert len(first) == len(second) == 6
    assert first[0].id == "address-2"
    assert first[-1].id == "address-0"
    assert first[-1].subtitle == "Место 0, Ленина 0, Москва"
    assert (first[0].latitude, first[0].longitude) == (56.838, 60.58)
    assert first[0].address_text == "Место 2, Ленина 2, Екатеринбург"
    assert [request.url.path for request in calls].count("/v1/geocode/search") == 1
    autocomplete = [request for request in calls if request.url.path.endswith("/autocomplete")]
    assert len(autocomplete) == 4
    assert all("filter" not in request.url.params for request in autocomplete)
    assert {request.url.params["bias"] for request in autocomplete} == {
        "proximity:60.6,56.84|countrycode:ru",
        "countrycode:ru",
    }
    assert all(request.url.params["apiKey"] == "test-key" for request in calls)
    assert all(request.url.host == "api.geoapify.com" for request in calls)


def test_nearby_town_and_suburb_are_not_discarded(
    monkeypatch: pytest.MonkeyPatch, member: tuple[Session, User]
) -> None:
    configured(monkeypatch)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/geocode/search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"city": "Екатеринбург", "country_code": "ru", "lat": 56.84, "lon": 60.6}
                    ]
                },
            )
        town = {**address(1, city="Берёзовский"), "town": "Берёзовский"}
        town.pop("city")
        suburb = {**address(2), "suburb": "Уралмаш"}
        return httpx.Response(200, json={"results": [town, suburb]})

    mock_client(monkeypatch, respond)
    session, user = member
    suggestions = product.suggest_locations(session, user, q="Ленина", city="ekb")
    assert [item.id for item in suggestions] == ["address-2", "address-1"]
    assert "Берёзовский" in suggestions[1].subtitle


def test_empty_local_response_still_returns_global_matches(
    monkeypatch: pytest.MonkeyPatch, member: tuple[Session, User]
) -> None:
    configured(monkeypatch)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/geocode/search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"city": "Екатеринбург", "country_code": "ru", "lat": 56.84, "lon": 60.6}
                    ]
                },
            )
        if request.url.params["bias"].startswith("proximity:"):
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"results": [address(3, city="Москва")]})

    mock_client(monkeypatch, respond)
    session, user = member
    suggestions = product.suggest_locations(session, user, q="Ленина", city="ekb")
    assert [item.id for item in suggestions] == ["address-3"]
    assert suggestions[0].address_text == "Место 3, Ленина 3, Москва"


def test_membership_short_query_and_missing_key(
    monkeypatch: pytest.MonkeyPatch, member: tuple[Session, User]
) -> None:
    session, user = member
    assert product.suggest_locations(session, user, q="  а ", city="ekb") == []
    with pytest.raises(HTTPException) as denied:
        product.suggest_locations(session, user, q="Тверская", city="msk")
    assert denied.value.status_code == 403
    monkeypatch.setattr(product, "settings", replace(product.settings, geoapify_api_key=""))
    with pytest.raises(HTTPException) as unavailable:
        product.suggest_locations(session, user, q="Ленина", city="ekb")
    assert unavailable.value.status_code == 503


@pytest.mark.parametrize("failure", ["timeout", "malformed"])
def test_provider_failures_are_controlled(
    monkeypatch: pytest.MonkeyPatch, member: tuple[Session, User], failure: str
) -> None:
    configured(monkeypatch)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/geocode/search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"city": "Екатеринбург", "country_code": "ru", "lat": 56.84, "lon": 60.6}
                    ]
                },
            )
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(200, json={"results": {"bad": "shape"}})

    mock_client(monkeypatch, respond)
    session, user = member
    with pytest.raises(HTTPException) as unavailable:
        product.suggest_locations(session, user, q="Ленина", city="ekb")
    assert unavailable.value.status_code == 503
