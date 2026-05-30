from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.errors import MissingAPIKeyError, ProviderError
from app.embeddings.base import BaseEmbeddingProvider
from app.schemas.embeddings import EmbeddingResult


class NvidiaEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "nvidia"

    def __init__(self, api_key: str | None, timeout_seconds: float, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = (base_url or "").rstrip("/")

    @property
    def endpoint(self) -> str:
        if not self.base_url:
            raise ProviderError(
                provider=self.provider_name,
                message="NVIDIA embedding endpoint is not configured.",
                retryable=True,
            )
        if self.base_url.endswith("/embeddings"):
            return self.base_url
        return f"{self.base_url}/embeddings"

    async def embed_text(self, text: str, model: str) -> EmbeddingResult:
        if not self.api_key:
            raise MissingAPIKeyError(self.provider_name)

        payload = {
            "model": model,
            "input": text,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                provider=self.provider_name,
                message="Embedding request timed out.",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                provider=self.provider_name,
                message="Network error while generating embedding.",
                retryable=True,
            ) from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderError(
                provider=self.provider_name,
                message="Embedding provider temporarily unavailable.",
                retryable=True,
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ProviderError(
                provider=self.provider_name,
                message="Embedding provider rejected request.",
                retryable=False,
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                provider=self.provider_name,
                message="Invalid embedding response format.",
                retryable=True,
                status_code=response.status_code,
            ) from exc

        vector = _extract_embedding_vector(data)
        if not vector:
            raise ProviderError(
                provider=self.provider_name,
                message="Embedding provider returned empty vector.",
                retryable=True,
                status_code=response.status_code,
            )
        usage_raw = data.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else None
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return EmbeddingResult(
            provider=self.provider_name,
            model=model,
            embedding=vector,
            dimensions=len(vector),
            usage=usage,
            latency_ms=latency_ms,
        )


def _extract_embedding_vector(payload: dict[str, Any]) -> list[float]:
    data_items = payload.get("data")
    if isinstance(data_items, list) and data_items:
        first = data_items[0]
        if isinstance(first, dict):
            raw = first.get("embedding")
            if isinstance(raw, list):
                return _coerce(raw)
    raw = payload.get("embedding")
    if isinstance(raw, list):
        return _coerce(raw)
    return []


def _coerce(values: list[Any]) -> list[float]:
    vector: list[float] = []
    for item in values:
        try:
            vector.append(float(item))
        except (TypeError, ValueError):
            return []
    return vector
