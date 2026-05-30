from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.embedding_service import generate_embedding
from app.core.errors import APIError
from app.deps import get_settings
from app.security.internal_auth import require_internal_admin


router = APIRouter(
    prefix="/internal/embeddings",
    tags=["internal-embeddings"],
    dependencies=[Depends(require_internal_admin)],
)


class InternalEmbeddingTestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    provider: str | None = None
    model: str | None = None


@router.post("/test")
async def test_embedding_provider(body: InternalEmbeddingTestRequest) -> dict:
    settings = get_settings()
    if not settings.embeddings_enabled:
        raise APIError(
            code="embedding_config_invalid",
            message="Embeddings are disabled.",
            status_code=400,
        )
    try:
        result = await generate_embedding(
            text=body.text,
            provider=body.provider,
            model=body.model,
        )
    except APIError:
        raise
    except Exception as exc:
        raise APIError(
            code="embedding_generation_failed",
            message="Failed to generate embedding.",
            status_code=502,
        ) from exc
    return {
        "ok": True,
        "provider": result.provider,
        "model": result.model,
        "dimensions": result.dimensions,
        "latency_ms": result.latency_ms,
    }
