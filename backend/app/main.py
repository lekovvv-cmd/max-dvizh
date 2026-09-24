from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="MAX ДВИЖ: Signal, private candidate choice, group reactions and final confirmation.",
)
app.include_router(api_router)
