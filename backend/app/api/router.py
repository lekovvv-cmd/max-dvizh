from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.product import router as product_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(product_router)
