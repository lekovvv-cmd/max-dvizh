"""One-shot production MAX webhook subscription setup and verification."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from app.core.config import settings

UPDATE_TYPES = ["bot_started", "message_callback", "bot_removed"]


def subscribe() -> None:
    if (
        not settings.max_bot_token
        or not settings.max_webhook_url
        or not settings.max_webhook_secret
    ):
        raise SystemExit("Set MAX_BOT_TOKEN, MAX_WEBHOOK_URL and MAX_WEBHOOK_SECRET")
    url = urlparse(settings.max_webhook_url)
    if url.scheme != "https" or not url.hostname or url.port not in {None, 443}:
        raise SystemExit("MAX_WEBHOOK_URL must be a public HTTPS URL on port 443")
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,256}", settings.max_webhook_secret):
        raise SystemExit("MAX_WEBHOOK_SECRET must match the MAX subscription contract")
    headers = {"Authorization": settings.max_bot_token}
    body = {
        "url": settings.max_webhook_url,
        "update_types": UPDATE_TYPES,
        "secret": settings.max_webhook_secret,
    }
    with httpx.Client(base_url=settings.max_bot_api_base, headers=headers, timeout=15) as client:
        response = client.post("/subscriptions", json=body)
        response.raise_for_status()
        if response.json().get("success") is not True:
            raise SystemExit("MAX did not accept the subscription")
        subscriptions = client.get("/subscriptions")
        subscriptions.raise_for_status()
        entries = subscriptions.json().get("subscriptions") or []
    if not any(
        item.get("url") == settings.max_webhook_url
        and set(UPDATE_TYPES).issubset(set(item.get("update_types") or []))
        for item in entries
    ):
        raise SystemExit("MAX subscription verification failed")
    print("MAX webhook subscription verified")


if __name__ == "__main__":
    subscribe()
