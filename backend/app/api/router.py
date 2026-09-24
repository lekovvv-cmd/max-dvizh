from fastapi import APIRouter

from app.api.routes.dvizh import router as dvizh_router
from app.api.routes.health import router as health_router
from app.api.routes.max_webhook import router as max_webhook_router
from app.api.routes.product import router as product_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(product_router)
api_router.include_router(dvizh_router)
api_router.include_router(max_webhook_router)
