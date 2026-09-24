"""MAX Mini App identity must come from signed initData in production."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth import service as auth


def signed_data(token: str, *, user_id: int = 123, auth_date: int | None = None) -> str:
    values = {
        "user": json.dumps({"id": user_id, "first_name": "Анна", "last_name": "К."}),
        "chat": json.dumps({"id": 77, "type": "CHAT"}),
        "auth_date": str(auth_date or int(datetime.now(UTC).timestamp())),
        "start_param": "dvizh_d1",
    }
    params = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, params.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_signed_max_init_data_and_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "settings", Settings(app_env="production", max_bot_token="token"))
    data = signed_data("token")
    assert auth.validate_init_data(data) == ("123", "Анна К.", "77")
    with pytest.raises(HTTPException) as error:
        auth.validate_init_data(data.replace("123", "456"))
    assert error.value.status_code == 401
    with pytest.raises(HTTPException) as error:
        auth.validate_init_data(signed_data("token", auth_date=1))
    assert error.value.status_code == 401


def test_demo_identity_is_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "settings", Settings(app_env="production", max_bot_token="token"))
    with Session(create_engine("sqlite://")) as session:
        with pytest.raises(HTTPException) as error:
            auth.current_user(session, x_max_init_data=None, x_demo_user="someone")
    assert error.value.status_code == 401
