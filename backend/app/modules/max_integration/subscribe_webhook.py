"""One-shot production MAX webhook subscription setup and verification."""

from __future__ import annotations

import httpx

from app.core.config import ConfigurationError, settings
from app.modules.max_integration.diagnostics import classify_failure, failure_summary

UPDATE_TYPES = ["bot_started", "message_callback", "bot_removed"]


def subscribe() -> None:
    try:
        settings.validate_webhook()
    except ConfigurationError as error:
        raise SystemExit(str(error)) from None
    headers = {"Authorization": settings.max_bot_token}
    body = {
        "url": settings.max_webhook_url,
        "update_types": UPDATE_TYPES,
        "secret": settings.max_webhook_secret,
    }
    try:
        with httpx.Client(
            base_url=settings.max_bot_api_base, headers=headers, timeout=15
        ) as client:
            # MAX documents POST as create/update for the URL, including secret rotation.
            response = client.post("/subscriptions", json=body)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get("success") is not True:
                raise SystemExit("MAX did not accept the subscription")
            subscriptions = client.get("/subscriptions")
            subscriptions.raise_for_status()
            result = subscriptions.json()
            entries = result.get("subscriptions") if isinstance(result, dict) else None
    except httpx.HTTPError as error:
        raise SystemExit(
            f"subscription_failed {failure_summary(classify_failure(error))}"
        ) from None
    except ValueError:
        raise SystemExit("subscription_failed reason=invalid_response_or_api_base") from None
    if not isinstance(entries, list):
        raise SystemExit("MAX subscription verification failed: invalid response")
    if not any(
        isinstance(item, dict)
        and item.get("url") == settings.max_webhook_url
        and isinstance(item.get("update_types"), list)
        and all(kind in item["update_types"] for kind in UPDATE_TYPES)
        for item in entries
    ):
        raise SystemExit("MAX subscription verification failed")
    print("MAX webhook subscription verified")


if __name__ == "__main__":
    subscribe()
