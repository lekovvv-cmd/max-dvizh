"""Read-only connectivity/token check: python -m app.modules.max_integration.diagnose."""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.modules.max_integration.diagnostics import classify_failure, failure_summary


def main() -> int:
    try:
        base = urlsplit(settings.max_bot_api_base)
        if (
            base.scheme != "https"
            or not base.hostname
            or base.username
            or base.password
            or base.query
            or base.fragment
        ):
            raise ValueError
        print(f"MAX_BOT_API_BASE={base.geturl()}")
    except ValueError:
        print(
            "success=false error_class=ConfigError message=MAX_BOT_API_BASE_must_be_HTTPS_without_credentials"
        )
        return 1
    print(f"MAX_BOT_TOKEN_set={bool(settings.max_bot_token)}")
    if not settings.max_bot_token:
        print("success=false error_class=ConfigError message=MAX_BOT_TOKEN_is_required")
        return 1
    try:
        response = httpx.get(
            f"{settings.max_bot_api_base.rstrip('/')}/me",
            headers={"Authorization": settings.max_bot_token},
            timeout=10,
        )
        response.raise_for_status()
        # Never print the response: it contains the bot's identity.
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("is_bot") is not True:
            raise ValueError
    except httpx.HTTPError as error:
        print(f"success=false {failure_summary(classify_failure(error))}")
        return 1
    except ValueError:
        print("success=false error_class=InvalidResponse message=Expected_MAX_bot_information")
        return 1
    print(f"success=true http_status={response.status_code} endpoint=/me")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
