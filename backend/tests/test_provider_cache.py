from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.modules.leisure.provider import (
    KudaGoProvider,
    NormalizedLeisureItem,
    ProviderQuery,
    RedisProviderCache,
    fetch_items,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def setex(self, key: str, _: int, value: str) -> None:
        self.values[key] = value


class RecordingProvider(KudaGoProvider):
    def __init__(self, items: list[NormalizedLeisureItem]) -> None:
        self.items_to_return = items
        self.calls = 0

    def items(self, query: ProviderQuery) -> list[NormalizedLeisureItem]:
        self.calls += 1
        assert query.city_slug == "ekb"
        return self.items_to_return


class FailingProvider(KudaGoProvider):
    def __init__(self) -> None:
        self.calls = 0

    def items(self, query: ProviderQuery) -> list[NormalizedLeisureItem]:
        self.calls += 1
        raise httpx.ConnectError("provider down")


def item() -> NormalizedLeisureItem:
    now = datetime.now(UTC)
    return NormalizedLeisureItem(
        provider="KUDAGO",
        provider_id="42",
        item_type="EVENT",
        city_slug="ekb",
        title="Квиз",
        category="other",
        venue_name=None,
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=4),
        latitude=56.8,
        longitude=60.6,
        price_text="500 ₽",
        price_min=500,
        source_url=None,
        image_url=None,
        source_fetched_at=now,
    )


def query() -> ProviderQuery:
    start = datetime(2026, 9, 17, 18, tzinfo=UTC)
    return ProviderQuery("ekb", start, start + timedelta(hours=4), ("concert",))


def test_source_recheck_distinguishes_cancelled_slot_closed_place_and_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = item()

    def response(data: dict[str, object], status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=data, request=httpx.Request("GET", "https://kudago.com"))

    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kwargs: response(
            {
                "id": 42,
                "dates": [
                    {
                        "start": int(source.starts_at.timestamp()),
                        "end": int(source.ends_at.timestamp()),
                    }
                ],
            }
        ),
    )
    assert KudaGoProvider().item_available("EVENT", "42", source.starts_at, source.ends_at)
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: response({"id": 42, "dates": []}))
    assert KudaGoProvider().item_available("EVENT", "42", source.starts_at, source.ends_at) is False
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: response({}, 404))
    assert KudaGoProvider().item_available("EVENT", "42", source.starts_at, source.ends_at) is False
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: response({"id": 42, "is_closed": True}))
    assert KudaGoProvider().item_available("PLACE", "42", source.starts_at, source.ends_at) is False

    def unavailable(url: str, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("source unavailable")

    monkeypatch.setattr(httpx, "get", unavailable)
    assert KudaGoProvider().item_available("EVENT", "42", source.starts_at, source.ends_at) is None
    assert (
        KudaGoProvider().item_available(
            "EVENT", "not-a-kudago-id", source.starts_at, source.ends_at
        )
        is None
    )


def test_redis_hit_skips_provider_and_miss_populates_cache() -> None:
    cache = RedisProviderCache(FakeRedis())
    provider = RecordingProvider([item()])

    first = fetch_items(query(), provider=provider, cache=cache)
    second = fetch_items(query(), provider=provider, cache=cache)

    assert not first.cached
    assert second.cached
    assert provider.calls == 1


def test_provider_failure_uses_cache_or_returns_honest_unavailable_result() -> None:
    cache = RedisProviderCache(FakeRedis())
    cache.set_events(query(), [item()])

    cached = fetch_items(query(), provider=FailingProvider(), cache=cache)
    missing = fetch_items(
        query(), provider=FailingProvider(), cache=RedisProviderCache(FakeRedis())
    )

    assert cached.cached and len(cached.items) == 1 and not cached.unavailable
    assert missing.items == [] and missing.unavailable


def test_cache_keys_partition_city_time_and_category_queries() -> None:
    first = query()
    second = ProviderQuery(
        first.city_slug, first.starts_at, first.ends_at + timedelta(hours=1), first.categories
    )
    third = ProviderQuery(first.city_slug, first.starts_at, first.ends_at, ())

    assert len({first.cache_key(), second.cache_key(), third.cache_key()}) == 3


def test_kudago_request_uses_the_same_city_time_category_slice(monkeypatch: object) -> None:
    captured: list[tuple[str, dict[str, object]]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[object]]:
            return {"results": []}

    def fake_get(url: str, *, params: dict[str, object], timeout: float) -> Response:
        captured.append((url, dict(params)))
        assert timeout > 0
        return Response()

    monkeypatch.setattr("app.modules.leisure.provider.httpx.get", fake_get)  # type: ignore[attr-defined]
    requested = query()
    KudaGoProvider().items(requested)

    assert len(captured) == 2
    events, places = captured
    assert events[0].endswith("/events/") and places[0].endswith("/places/")
    assert events[1]["location"] == places[1]["location"] == "ekb"
    assert events[1]["actual_since"] == int(requested.starts_at.timestamp())
    assert events[1]["actual_until"] == int(requested.ends_at.timestamp())
    assert events[1]["categories"] == "concert,party"
    assert places[1]["categories"] == "clubs,concert-hall"


def test_wellness_query_uses_real_place_slugs_without_unfiltered_events(
    monkeypatch: object,
) -> None:
    captured: list[tuple[str, dict[str, object]]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[object]]:
            return {"results": []}

    def fake_get(url: str, *, params: dict[str, object], timeout: float) -> Response:
        captured.append((url, dict(params)))
        return Response()

    monkeypatch.setattr("app.modules.leisure.provider.httpx.get", fake_get)  # type: ignore[attr-defined]
    requested = query()
    KudaGoProvider().items(
        ProviderQuery(requested.city_slug, requested.starts_at, requested.ends_at, ("wellness",))
    )
    assert len(captured) == 1
    assert captured[0][0].endswith("/places/")
    assert captured[0][1]["categories"] == "amusement,recreation,salons,suburb"


def test_museum_query_reads_only_matching_places(monkeypatch: object) -> None:
    captured: list[tuple[str, dict[str, object]]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[object]]:
            return {"results": []}

    def fake_get(url: str, *, params: dict[str, object], timeout: float) -> Response:
        captured.append((url, dict(params)))
        return Response()

    monkeypatch.setattr("app.modules.leisure.provider.httpx.get", fake_get)  # type: ignore[attr-defined]
    requested = query()
    KudaGoProvider().items(
        ProviderQuery(requested.city_slug, requested.starts_at, requested.ends_at, ("museum",))
    )
    assert len(captured) == 1
    assert captured[0][0].endswith("/places/")
    assert captured[0][1]["categories"] == "museums"


def test_product_search_keeps_verified_places_when_one_provider_call_times_out(
    monkeypatch: object,
) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "results": [
                    {
                        "id": 42,
                        "title": "Кафе у парка",
                        "categories": ["restaurants"],
                        "site_url": "https://kudago.com/place/42/",
                        "is_closed": False,
                        "timetable": "ежедневно 10:00–23:00",
                    }
                ],
                "next": None,
            }

    def fake_get(url: str, *, params: dict[str, object], timeout: float) -> Response:
        if url.endswith("/search/"):
            raise httpx.ConnectTimeout("search timed out")
        return Response()

    monkeypatch.setattr("app.modules.leisure.provider.httpx.get", fake_get)  # type: ignore[attr-defined]
    requested = query()
    found = KudaGoProvider().product_items(
        ProviderQuery(
            requested.city_slug,
            requested.starts_at,
            requested.ends_at,
            ("bar", "restaurant"),
            product=True,
        )
    )
    assert len(found) == 1
    assert found[0].categories == ("restaurant",)


def test_product_search_reports_unavailable_when_every_provider_call_fails(
    monkeypatch: object,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectTimeout("provider timed out")

    monkeypatch.setattr("app.modules.leisure.provider.httpx.get", fail)  # type: ignore[attr-defined]
    requested = query()
    with pytest.raises(httpx.ConnectTimeout):
        KudaGoProvider().product_items(
            ProviderQuery(
                requested.city_slug, requested.starts_at, requested.ends_at, ("bar",), product=True
            )
        )
