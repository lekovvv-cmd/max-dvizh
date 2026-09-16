from datetime import UTC, datetime, timedelta

import httpx

from app.modules.leisure.provider import (
    KudaGoProvider,
    NormalizedLeisureItem,
    RedisProviderCache,
    fetch_city_items,
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

    def items(self, city: str) -> list[NormalizedLeisureItem]:
        self.calls += 1
        assert city == "ekb"
        return self.items_to_return


class FailingProvider(KudaGoProvider):
    def __init__(self) -> None:
        self.calls = 0

    def items(self, city: str) -> list[NormalizedLeisureItem]:
        self.calls += 1
        raise httpx.ConnectError("provider down")


def item() -> NormalizedLeisureItem:
    now = datetime.now(UTC)
    return NormalizedLeisureItem(
        provider="KUDAGO", provider_id="42", item_type="EVENT", city_slug="ekb", title="Квиз",
        category="other", venue_name=None, starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=4), latitude=56.8, longitude=60.6, price_text="500 ₽",
        price_min=500, source_url=None, image_url=None, source_fetched_at=now,
    )


def test_redis_hit_skips_provider_and_miss_populates_cache() -> None:
    cache = RedisProviderCache(FakeRedis())
    provider = RecordingProvider([item()])

    first = fetch_city_items("ekb", provider=provider, cache=cache)
    second = fetch_city_items("ekb", provider=provider, cache=cache)

    assert not first.cached
    assert second.cached
    assert provider.calls == 1


def test_provider_failure_uses_cache_or_returns_honest_unavailable_result() -> None:
    cache = RedisProviderCache(FakeRedis())
    cache.set_events("ekb", [item()])

    cached = fetch_city_items("ekb", provider=FailingProvider(), cache=cache)
    missing = fetch_city_items("ekb", provider=FailingProvider(), cache=RedisProviderCache(FakeRedis()))

    assert cached.cached and len(cached.items) == 1 and not cached.unavailable
    assert missing.items == [] and missing.unavailable
