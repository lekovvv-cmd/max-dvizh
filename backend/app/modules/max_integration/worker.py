"""Small independent outbox process; run from the same backend image."""

from __future__ import annotations

import logging
import time

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.models import OutboxNotification
from app.db.session import SessionLocal
from app.modules.max_integration.client import dispatch_pending

logger = logging.getLogger(__name__)


def run() -> None:
    if not settings.max_bot_token and settings.app_env != "development":
        raise SystemExit("MAX_BOT_TOKEN is required for APP_PROCESS=worker")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.max_bot_token:
        logger.warning("outbox_delivery_disabled reason=missing_token development_mode=true")
    logger.info("outbox_worker_started poll_seconds=%s", settings.outbox_poll_seconds)
    next_heartbeat = 0.0
    while True:
        try:
            with SessionLocal() as session:
                delivered = dispatch_pending(session)
                if time.monotonic() >= next_heartbeat:
                    pending = session.scalar(
                        select(func.count())
                        .select_from(OutboxNotification)
                        .where(OutboxNotification.status == "PENDING")
                    )
                    failed = session.scalar(
                        select(func.count())
                        .select_from(OutboxNotification)
                        .where(OutboxNotification.status == "FAILED")
                    )
                    logger.info(
                        "outbox_heartbeat pending=%s failed=%s delivered=%s",
                        pending,
                        failed,
                        delivered,
                    )
                    next_heartbeat = time.monotonic() + 60
        except SQLAlchemyError:
            logger.exception("outbox_database_error")
        time.sleep(settings.outbox_poll_seconds)


if __name__ == "__main__":
    run()
