from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.errors import APIError
from app.deps import get_settings
from app.security.auth import require_api_key
from app.storage.db import get_connection


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    settings = get_settings()
    if settings.require_api_key and not settings.public_health:
        require_api_key(request)
    return {
        "status": "ok",
        "service": "nesty-ai",
        "version": settings.app_version,
    }


@router.get("/ready")
async def readiness_check(request: Request) -> dict[str, str]:
    settings = get_settings()
    if settings.require_api_key and not settings.public_health:
        require_api_key(request)
    try:
        with get_connection(settings.nesty_db_path) as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:
        raise APIError(
            code="provider_unavailable",
            message="Service is not ready.",
            status_code=503,
            details={"database": "error"},
        ) from exc

    return {
        "status": "ready",
        "service": "nesty-ai",
        "database": "ok",
    }

