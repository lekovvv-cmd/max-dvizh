from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, settings
from app.db.session import engine

router = APIRouter(tags=["technical"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """Liveness endpoint intentionally independent from product modules."""
    return {
        "status": "ok",
        "service": "backend",
        "version": settings.app_version,
    }


@router.get("/health/ready")
def readiness() -> dict[str, str]:
    """Readiness covers local API configuration and PostgreSQL, not MAX reachability."""
    try:
        settings.validate_process("api")
    except ConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready",
        ) from error

    return {"status": "ready", "database": "ok"}
