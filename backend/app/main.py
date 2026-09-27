import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.validate_process("api")
    if not settings.max_bot_username:
        logging.getLogger(__name__).warning("max_deep_links_disabled reason=missing_bot_username")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="MAX ДВИЖ: Signal, private candidate choice, group reactions and final confirmation.",
    lifespan=lifespan,
)
app.include_router(api_router)
