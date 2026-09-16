"""KudaGo adapter: normalization, provenance and last-successful snapshot fallback."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import LeisureItem, ProviderSnapshot


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_price(value: str | None, is_free: bool) -> int | None:
    if is_free:
        return 0
    if not value:
        return None
    numbers = re.findall(r"(?<!\d)(\d{1,6})(?!\d)", value.replace(" ", ""))
    return int(numbers[0]) if len(numbers) == 1 else None


def normalize_event(
    raw: dict[str, Any], city: str, fetched_at: datetime
) -> dict[str, object] | None:
    dates = raw.get("dates") or []
    date = next((item for item in dates if item.get("start")), None)
    if date is None:
        return None
    start = datetime.fromtimestamp(int(date["start"]), UTC)
    end = datetime.fromtimestamp(int(date.get("end") or date["start"]) + 7200, UTC)
    place = raw.get("place") or {}
    coords = place.get("coords") or raw.get("coords") or {}
    categories = raw.get("categories") or []
    price_text = raw.get("price") or None
    free = bool(raw.get("is_free", False))
    return {
        "provider": "KUDAGO",
        "provider_id": str(raw["id"]),
        "item_type": "EVENT",
        "city_slug": city,
        "title": str(raw.get("title") or "Событие KudaGo"),
        "category": str(categories[0] if categories else "other"),
        "venue_name": place.get("title"),
        "latitude": coords.get("lat"),
        "longitude": coords.get("lon"),
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "price_text": price_text,
        "price_min": parse_price(price_text, free),
        "is_free": free,
        "source_url": raw.get("site_url"),
        "image_url": ((raw.get("images") or [{}])[0] or {}).get("image"),
        "source_fetched_at": fetched_at.isoformat(),
        "is_demo": False,
        "raw_metadata": {"source": "KudaGo"},
    }


class KudaGoProvider:
    def cities(self) -> list[dict[str, str]]:
        response = httpx.get(
            f"{settings.kudago_base_url}/locations/",
            params={"lang": "ru"},
            timeout=settings.kudago_timeout_seconds,
        )
        response.raise_for_status()
        return [{"slug": str(city["slug"]), "name": str(city["name"])} for city in response.json()]

    def items(self, city: str) -> list[dict[str, object]]:
        now = utcnow()
        response = httpx.get(
            f"{settings.kudago_base_url}/events/",
            params={
                "location": city,
                "actual_since": int(now.timestamp()),
                "page_size": 100,
                "fields": "id,title,dates,place,categories,price,is_free,site_url,images",
            },
            timeout=settings.kudago_timeout_seconds,
        )
        response.raise_for_status()
        return [
            item
            for raw in response.json().get("results", [])
            if (item := normalize_event(raw, city, now))
        ]


def _persist_items(session: Session, records: list[dict[str, object]]) -> list[LeisureItem]:
    result: list[LeisureItem] = []
    for record in records:
        existing = session.scalar(
            select(LeisureItem).where(
                LeisureItem.provider == record["provider"],
                LeisureItem.provider_id == record["provider_id"],
            )
        )
        values = dict(record)
        for field in ("starts_at", "ends_at", "source_fetched_at"):
            values[field] = datetime.fromisoformat(str(values[field]))
        if existing is None:
            existing = LeisureItem(**values)  # type: ignore[arg-type]
            session.add(existing)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
        result.append(existing)
    session.flush()
    return result


def sync_city(session: Session, city: str) -> tuple[list[LeisureItem], bool, datetime | None]:
    """Return live items or last successful snapshot; failures never become disguised demo data."""
    try:
        records = KudaGoProvider().items(city)
        snapshot = session.scalar(
            select(ProviderSnapshot).where(
                ProviderSnapshot.provider == "KUDAGO", ProviderSnapshot.city_slug == city
            )
        )
        if snapshot is None:
            snapshot = ProviderSnapshot(
                provider="KUDAGO", city_slug=city, payload=records, fetched_at=utcnow()
            )
            session.add(snapshot)
        else:
            snapshot.payload, snapshot.fetched_at = records, utcnow()
        session.commit()
        return _persist_items(session, records), False, snapshot.fetched_at
    except (httpx.HTTPError, ValueError):
        session.rollback()
        snapshot = session.scalar(
            select(ProviderSnapshot).where(
                ProviderSnapshot.provider == "KUDAGO", ProviderSnapshot.city_slug == city
            )
        )
        if snapshot is None:
            return [], False, None
        return _persist_items(session, snapshot.payload), True, snapshot.fetched_at


def cached_city_items(session: Session, city: str) -> list[LeisureItem]:
    cutoff = utcnow() - timedelta(days=1)
    return list(
        session.scalars(
            select(LeisureItem).where(LeisureItem.city_slug == city, LeisureItem.starts_at > cutoff)
        )
    )
