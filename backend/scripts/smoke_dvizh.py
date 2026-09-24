"""Exercise the real local API and KudaGo path with three demo users.

Run against a disposable development database, for example a Compose backend
published on port 8001: `DVIZH_SMOKE_URL=http://127.0.0.1:8001 python -m scripts.smoke_dvizh`.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx


def main() -> None:
    base = os.environ.get("DVIZH_SMOKE_URL", "http://127.0.0.1:8001").rstrip("/")
    prefix = f"smoke-{uuid4().hex[:8]}"
    users = [f"{prefix}-{name}" for name in ("anya", "borya", "vera")]

    def call(
        method: str,
        path: str,
        user: str,
        body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {"X-Demo-User": user}
        if request_id:
            headers["X-Request-ID"] = request_id
        response = httpx.request(
            method, f"{base}/api/v1{path}", headers=headers, json=body, timeout=45
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    group = call("POST", "/groups", users[0], {"name": prefix, "city_slug": "msk"})
    for user in users[1:]:
        call("POST", f"/groups/join/{group['invite_token']}", user)
    local = datetime.now(ZoneInfo("Europe/Moscow")) + timedelta(days=1)
    start = local.replace(hour=16, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=3)
    request_id = str(uuid4())
    body = {
        "group_ids": [group["id"]],
        "activity_categories": ["quest"],
        "available_from": start.isoformat(),
        "available_to": end.isoformat(),
        "min_people": 3,
        "max_people": 3,
    }
    created = call("POST", "/signals", users[0], body, request_id)
    repeated = call("POST", "/signals", users[0], body, request_id)
    assert created["signal_batch_id"] == repeated["signal_batch_id"]
    dvizh = created["dvizhi"][0]
    print(f"Provider state: {dvizh['status']}; candidates: {len(dvizh['candidates'])}")
    assert dvizh["status"] == "CHOOSING_CANDIDATES", dvizh["status"]
    assert dvizh["candidates"], "KudaGo returned no verified quest candidates"
    identifier = dvizh["id"]
    try:
        call("GET", f"/dvizhi/{identifier}", users[1])
    except httpx.HTTPStatusError as error:
        assert error.response.status_code == 404
    else:
        raise AssertionError("A private round was visible before launch")

    candidate = next(item for item in dvizh["candidates"] if item["compatibility"] == "EXACT")
    path = f"/dvizhi/{identifier}/candidates/{candidate['id']}/reaction"
    call("PUT", path, users[0], {"value": "WOULD_GO"})
    launched = call("POST", f"/dvizhi/{identifier}/launch", users[0])
    assert launched["status"] == "COLLECTING_REACTIONS", launched["status"]
    for user in users[1:]:
        state = call("GET", f"/dvizhi/{identifier}", user)
        assert state["participants"] == []
        assert state["candidates"]
        state = call("PUT", path, user, {"value": "WOULD_GO"})
    assert state["status"] == "AWAITING_CONFIRMATION", state["status"]
    assert state["participants"] == []
    for user in users:
        state = call(
            "POST", f"/dvizhi/{identifier}/confirm", user, {"candidate_id": candidate["id"]}
        )
    assert state["status"] == "GATHERED", state["status"]
    assert state["confirmed_count"] == 3
    assert len(state["participants"]) == 3
    print(f"PASS: {identifier} / {candidate['title']} / 3 confirmed")


if __name__ == "__main__":
    main()
