from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.errors import APIError
from app.core.provider_diagnostics import diagnose_all_model_aliases, diagnose_model_alias, diagnose_provider_model
from app.deps import get_settings
from app.security.internal_auth import require_internal_admin
from app.storage.provider_health import get_latest_provider_health, list_provider_health_checks, summarize_provider_health


router = APIRouter(
    prefix="/internal/diagnostics",
    tags=["internal-diagnostics"],
    dependencies=[Depends(require_internal_admin)],
)


class ProviderHealthCheckRequest(BaseModel):
    model_alias: str | None = None
    include_roles: bool = True
    message: str = Field(default="Reply with exactly: OK", min_length=1, max_length=200)
    dry_run: bool = False


class ProviderModelCheckRequest(BaseModel):
    provider: str
    model: str
    message: str = Field(default="Reply with exactly: OK", min_length=1, max_length=200)
    model_alias: str | None = None
    role: str | None = None
    dry_run: bool = False


def _require_diagnostics_enabled() -> None:
    settings = get_settings()
    if bool(getattr(settings, "diagnostics_enabled", True)):
        return
    raise APIError(
        code="diagnostics_disabled",
        message="Not Found.",
        status_code=404,
    )


@router.get("/provider-health")
async def list_provider_health_endpoint(
    provider: str | None = None,
    model_alias: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    _require_diagnostics_enabled()
    if limit < 1 or limit > 200 or offset < 0:
        raise APIError(
            code="invalid_diagnostic_request",
            message="Invalid diagnostics pagination parameters.",
            status_code=400,
        )
    rows = list_provider_health_checks(
        provider=provider,
        model_alias=model_alias,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "object": "list",
        "data": rows,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(rows),
            "has_more": len(rows) >= limit,
        },
    }


@router.get("/provider-health/latest")
async def latest_provider_health_endpoint(provider: str | None = None, model_alias: str | None = None) -> dict:
    _require_diagnostics_enabled()
    rows = get_latest_provider_health(provider=provider, model_alias=model_alias)
    summary = summarize_provider_health()
    return {
        "object": "list",
        "data": rows,
        "summary": summary,
    }


@router.post("/provider-health/check")
async def run_provider_health_check_endpoint(body: ProviderHealthCheckRequest) -> dict:
    _require_diagnostics_enabled()
    model_alias = str(body.model_alias or "").strip()
    if model_alias:
        result = await diagnose_model_alias(
            model_alias=model_alias,
            include_roles=bool(body.include_roles),
            message=body.message,
            dry_run=bool(body.dry_run),
        )
    else:
        result = await diagnose_all_model_aliases(
            message=body.message,
            include_roles=bool(body.include_roles),
            dry_run=bool(body.dry_run),
        )
    return {"ok": True, "result": result}


@router.post("/provider-model/check")
async def run_provider_model_check_endpoint(body: ProviderModelCheckRequest) -> dict:
    _require_diagnostics_enabled()
    provider = str(body.provider or "").strip().lower()
    model = str(body.model or "").strip()
    if not provider or not model:
        raise APIError(
            code="invalid_diagnostic_request",
            message="Provider and model are required.",
            status_code=400,
        )
    result = await diagnose_provider_model(
        provider=provider,
        model=model,
        message=body.message,
        model_alias=body.model_alias,
        role=body.role,
        dry_run=bool(body.dry_run),
    )
    return {"ok": True, "result": result}
