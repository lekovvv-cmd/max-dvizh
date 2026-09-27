"""Safe MAX failure metadata shared by delivery logs and management commands."""

from __future__ import annotations

import json
import socket
import ssl
from dataclasses import dataclass

import httpx

# Never copy arbitrary MAX messages: they can echo tokens, recipients or payloads.
SAFE_RESPONSE_CODES = frozenset(
    {
        "access.denied",
        "chat.denied",
        "chat.not.found",
        "user.not.found",
        "user.not.available",
        "recipient.not.found",
        "invalid.recipient",
        "attachment.not.ready",
        "too.many.requests",
    }
)
RECIPIENT_CODES = frozenset(
    {
        "chat.denied",
        "chat.not.found",
        "user.not.found",
        "user.not.available",
        "recipient.not.found",
        "invalid.recipient",
    }
)


@dataclass(frozen=True)
class MaxFailure:
    error_class: str
    reason: str
    http_status: int | None
    endpoint: str
    message: str
    response_body: str
    retryable: bool


def classify_failure(error: httpx.HTTPError) -> MaxFailure:
    try:
        path = error.request.url.path
    except RuntimeError:
        path = "unknown"
    endpoint = path if path in {"/me", "/messages", "/answers", "/subscriptions"} else "other"
    status = None
    body = "omitted"
    retryable = True
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        try:
            payload = error.response.json()
        except ValueError:
            payload = None
        code = payload.get("code") if isinstance(payload, dict) else None
        if isinstance(code, str) and code in SAFE_RESPONSE_CODES:
            body = json.dumps({"code": code}, separators=(",", ":"))
        reason = (
            "invalid_recipient"
            if isinstance(code, str) and code in RECIPIENT_CODES
            else f"http_{status}"
        )
        message = "MAX rejected the request"
        retryable = not (400 <= status < 500 and status != 429)
    else:
        chain: list[BaseException] = []
        cause: BaseException | None = error
        while cause is not None and len(chain) < 10:
            chain.append(cause)
            cause = cause.__cause__ or cause.__context__
        # The string is inspected only; none of it is ever emitted to logs.
        description = " ".join(str(item).lower() for item in chain)
        if any(isinstance(item, ssl.SSLError) for item in chain) or any(
            marker in description
            for marker in ("certificate verify failed", "certificate_verify_failed", "ssl:", "tls")
        ):
            reason, message = "tls", "TLS certificate or handshake failure"
        elif any(isinstance(item, socket.gaierror) for item in chain) or any(
            marker in description
            for marker in (
                "getaddrinfo",
                "name resolution",
                "name or service not known",
                "nodename nor servname",
            )
        ):
            reason, message = "dns", "DNS resolution failed"
        elif isinstance(error, httpx.ConnectTimeout):
            reason, message = "connect_timeout", "Connection timed out"
        elif isinstance(error, httpx.ReadTimeout):
            reason, message = "read_timeout", "Response timed out"
        elif isinstance(error, httpx.TimeoutException):
            reason, message = "timeout", "MAX request timed out"
        elif isinstance(error, httpx.ConnectError):
            reason, message = "connect", "Connection failed"
        else:
            reason, message = "transport", "MAX transport failure"
    return MaxFailure(type(error).__name__, reason, status, endpoint, message, body, retryable)


def failure_summary(failure: MaxFailure) -> str:
    return (
        f"error_class={failure.error_class} reason={failure.reason} "
        f"http_status={failure.http_status} endpoint={failure.endpoint} "
        f"message={failure.message!r} response_body={failure.response_body}"
    )
