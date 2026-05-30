from __future__ import annotations

import hashlib
from typing import Any

from app.config import Settings
from app.core.errors import APIError
from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings.nvidia import NvidiaEmbeddingProvider
from app.embeddings.openrouter import OpenRouterEmbeddingProvider
from app.schemas.embeddings import EmbeddingResult


class NoOpEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "noop"

    async def embed_text(self, text: str, model: str) -> EmbeddingResult:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [round((byte / 255.0), 6) for byte in digest[:8]]
        return EmbeddingResult(
            provider=self.provider_name,
            model=model,
            embedding=vector,
            dimensions=len(vector),
            usage=None,
            latency_ms=0,
        )


def build_embedding_provider(
    settings: Settings,
    provider_name: str | None = None,
) -> BaseEmbeddingProvider:
    selected = str(provider_name or settings.embeddings_provider or "").strip().lower()
    if selected == "openrouter":
        return OpenRouterEmbeddingProvider(
            api_key=settings.openrouter_api_key,
            timeout_seconds=settings.embeddings_timeout_seconds,
        )
    if selected == "nvidia":
        return NvidiaEmbeddingProvider(
            api_key=settings.nvidia_api_key,
            timeout_seconds=settings.embeddings_timeout_seconds,
            base_url=settings.nvidia_base_url,
        )
    if selected == "noop":
        return NoOpEmbeddingProvider()
    raise APIError(
        code="embedding_config_invalid",
        message="Unsupported embeddings provider configured.",
        status_code=400,
        details={"provider": selected},
    )


def sanitize_embedding_usage(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None
    cleaned: dict[str, Any] = {}
    for key in ("prompt_tokens", "total_tokens", "input_tokens"):
        if key in usage:
            try:
                cleaned[key] = int(usage[key])
            except (TypeError, ValueError):
                continue
    return cleaned or None
