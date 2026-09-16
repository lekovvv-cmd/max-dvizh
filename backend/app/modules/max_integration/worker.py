"""Small independent outbox process; run from the same backend image."""

from __future__ import annotations

import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.max_integration.client import dispatch_pending


def run() -> None:
    while True:
        with SessionLocal() as session:
            dispatch_pending(session)
        time.sleep(settings.outbox_poll_seconds)


if __name__ == "__main__":
    run()
