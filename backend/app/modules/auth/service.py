"""MAX initData validation and deliberately constrained development identity."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import unquote_plus

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import get_session


def _fail(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def validate_init_data(init_data: str) -> tuple[str, str, str | None]:
    """Implement the current MAX documented two-stage HMAC validation."""
    if not settings.max_bot_token:
        raise _fail("MAX_BOT_TOKEN is not configured")
    chunks = init_data.split("&")
    pairs: list[tuple[str, str]] = []
    for chunk in chunks:
        if "=" not in chunk:
            raise _fail("Malformed MAX initData")
        key, value = chunk.split("=", 1)
        pairs.append((key, unquote_plus(value)))
    if sum(key == "hash" for key, _ in pairs) != 1:
        raise _fail("MAX initData must contain exactly one hash")
    original_hash = next(value for key, value in pairs if key == "hash")
    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(pairs) if key != "hash")
    secret = hmac.new(b"WebAppData", settings.max_bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, launch_params.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, original_hash):
        raise _fail("Invalid MAX initData signature")
    values = dict(pairs)
    try:
        auth_date = datetime.fromtimestamp(int(values["auth_date"]), tz=UTC)
        user = json.loads(values["user"])
        max_user_id = str(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise _fail("Malformed MAX user data") from error
    if (datetime.now(UTC) - auth_date).total_seconds() > settings.max_init_data_age_seconds:
        raise _fail("MAX launch data has expired")
    name = (
        " ".join(part for part in [user.get("first_name"), user.get("last_name")] if part)
        or "Участник"
    )
    try:
        chat = json.loads(values["chat"]) if values.get("chat") else None
        chat_id = str(chat["id"]) if isinstance(chat, dict) and chat.get("type") == "CHAT" else None
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise _fail("Malformed MAX chat data") from error
    return max_user_id, name, chat_id


def current_user(
    session: Annotated[Session, Depends(get_session)],
    x_max_init_data: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
) -> User:
    """No client supplied user id is trusted in production; demo is development-only."""
    chat_id: str | None = None
    if x_max_init_data:
        max_user_id, name, chat_id = validate_init_data(x_max_init_data)
    elif settings.app_env == "development" and x_demo_user:
        max_user_id, name = x_demo_user.strip(), f"Демо {x_demo_user.strip()}"
    else:
        raise _fail("Open through MAX or use X-Demo-User in local development")
    if not max_user_id:
        raise _fail("Invalid user identity")
    user = session.scalar(select(User).where(User.max_user_id == max_user_id))
    if user is None:
        created = User(max_user_id=max_user_id, display_name=name)
        try:
            # A second first-launch request can race the initial SELECT. Keep
            # the outer transaction usable when the unique constraint wins.
            with session.begin_nested():
                session.add(created)
                session.flush()
        except IntegrityError:
            user = session.scalar(select(User).where(User.max_user_id == max_user_id))
            if user is None:
                raise
        else:
            session.commit()
            session.refresh(created)
            user = created
    if user.display_name != name and x_max_init_data:
        user.display_name = name
        session.commit()
    return user


def optional_max_chat_id(x_max_init_data: str | None) -> str | None:
    if not x_max_init_data:
        return None
    return validate_init_data(x_max_init_data)[2]
