from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Technical bootstrap API. Product contracts are introduced in later milestones.",
)
app.include_router(api_router)
