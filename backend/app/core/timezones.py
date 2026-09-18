"""Interpret provider city zones and stored IANA zones for local display."""

from __future__ import annotations

import re
from datetime import UTC, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def display_timezone(value: str | None) -> tzinfo:
    if not value:
        return UTC
    match = re.fullmatch(r"GMT([+-])(\d{2}):(\d{2})", value)
    if match:
        hours, minutes = int(match.group(2)), int(match.group(3))
        if hours <= 23 and minutes <= 59:
            offset = timedelta(hours=hours, minutes=minutes)
            return timezone(offset if match.group(1) == "+" else -offset)
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC
