import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.domain_errors import DomainError, domain_error_response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.validate_process("api")
    if not (settings.max_bot_token and settings.max_webhook_url and settings.max_webhook_secret):
        logging.getLogger(__name__).warning("max_webhook_not_configured")
    if not settings.max_bot_username:
        logging.getLogger(__name__).warning("max_deep_links_disabled reason=missing_bot_username")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="MAX ДВИЖ: Signal, private candidate choice, group reactions and final confirmation.",
    lifespan=lifespan,
)
app.add_exception_handler(DomainError, domain_error_response)
app.include_router(api_router)
