"""Supported cities are local data, independent of the leisure provider."""

from app.modules.leisure.cities import CITIES, GEOAPIFY_ONLY_CITIES
from app.modules.leisure.geoapify import city_name


def test_tyumen_is_supported_by_local_catalog() -> None:
    assert CITIES["tmn"] == {
        "slug": "tmn",
        "name": "Тюмень",
        "timezone": "Asia/Yekaterinburg",
    }
    assert "tmn" in GEOAPIFY_ONLY_CITIES
    assert city_name("tmn") == "Тюмень"
