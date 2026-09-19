from datetime import UTC, datetime

from app.modules.leisure.provider import (
    ProviderQuery,
    normalize_event,
    normalize_events,
    normalize_place,
    price_kind,
)


def test_provider_end_is_preserved_and_missing_end_is_unverified() -> None:
    fetched = datetime(2026, 9, 16, tzinfo=UTC)
    explicit = normalize_event(
        {"id": 1, "dates": [{"start": 1_789_600_000, "end": 1_789_603_600}]}, "ekb", fetched
    )
    fallback = normalize_event({"id": 2, "dates": [{"start": 1_789_600_000}]}, "ekb", fetched)
    assert explicit is not None and explicit.ends_at.timestamp() == 1_789_603_600
    assert fallback is None


def test_every_documented_occurrence_becomes_concrete_item() -> None:
    fetched = datetime(2026, 9, 16, tzinfo=UTC)
    raw = {
        "id": 42,
        "categories": ["quest", "concert"],
        "place": {"title": "Клуб", "coords": {"lat": 56.8, "lon": 60.6}},
        "dates": [
            {"start": 1_789_600_000, "end": 1_789_603_600},
            {"start": 1_789_686_400, "end": 1_789_690_000},
        ],
    }
    items = normalize_events(raw, "ekb", fetched)
    assert len(items) == 2
    assert items[0].starts_at != items[1].starts_at
    assert set(items[0].categories) == {"games", "concert"}
    assert items[0].latitude == 56.8


def test_place_and_price_floor_are_explicitly_uncertain() -> None:
    fetched = datetime(2026, 9, 16, tzinfo=UTC)
    query = ProviderQuery("ekb", fetched, fetched.replace(day=17))
    place = normalize_place(
        {
            "id": 1,
            "title": "Антикафе",
            "categories": ["anticafe"],
            "site_url": "https://kudago.com/place/1/",
            "address": "Улица 1",
            "coords": {"lat": 56.8, "lon": 60.6},
        },
        query,
        fetched,
    )
    assert place is not None and place.item_type == "PLACE"
    assert place.opening_hours_unverified and place.address_text == "Улица 1"
    assert place.categories == ("games",)
    assert price_kind("от 400 ₽", False) == ("FROM", 400)
    assert price_kind(None, False) == ("UNKNOWN", None)


def test_wellness_taxonomy_uses_verified_place_categories_and_content() -> None:
    fetched = datetime(2026, 9, 16, tzinfo=UTC)
    query = ProviderQuery("msk", fetched, fetched.replace(day=17), ("wellness",))
    bath = normalize_place(
        {
            "id": 2,
            "title": "GREMM-курорт",
            "categories": ["amusement", "salons"],
            "description": "Панорамная баня и термы",
            "site_url": "https://kudago.com/msk/place/gremm/",
        },
        query,
        fetched,
    )
    manicure = normalize_place(
        {
            "id": 3,
            "title": "Маникюр",
            "categories": ["salons"],
            "description": "Ногти",
            "site_url": "https://kudago.com/msk/place/nails/",
        },
        query,
        fetched,
    )
    bedroom = normalize_place(
        {
            "id": 4,
            "title": "Дом вверх дном",
            "categories": ["amusement"],
            "description": "В доме есть спальня",
            "site_url": "https://kudago.com/ekb/place/house/",
        },
        query,
        fetched,
    )
    assert bath is not None and "wellness" in bath.categories
    assert manicure is not None and "wellness" not in manicure.categories
    assert bedroom is not None and "wellness" not in bedroom.categories


def test_provider_discards_missing_or_invalid_dates_and_uses_first_valid_entry() -> None:
    fetched = datetime(2026, 9, 16, tzinfo=UTC)
    assert normalize_event({"id": 1, "dates": []}, "ekb", fetched) is None
    assert normalize_event({"id": 1, "dates": [{"start": 10, "end": 10}]}, "ekb", fetched) is None
    item = normalize_event(
        {"id": 1, "dates": [{}, {"start": 1_789_600_000, "end": 1_789_603_600}]}, "ekb", fetched
    )
    assert item is not None and item.starts_at.timestamp() == 1_789_600_000
