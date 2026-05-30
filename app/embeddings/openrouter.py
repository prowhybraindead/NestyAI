from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.errors import MissingAPIKeyError, ProviderError
from app.embeddings.base import BaseEmbeddingProvider
from app.schemas.embeddings import EmbeddingResult


class OpenRouterEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "openrouter"

    def __init__(self, api_key: str | None, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.endpoint = "https://openrouter.ai/api/v1/embeddings"

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

        embedding = _extract_embedding_vector(data)
        dimensions = len(embedding)
        if dimensions <= 0:
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
            embedding=embedding,
            dimensions=dimensions,
            usage=usage,
            latency_ms=latency_ms,
        )

    async def embed_batch(self, texts: list[str], model: str) -> list[EmbeddingResult]:
        if not self.api_key:
            raise MissingAPIKeyError(self.provider_name)
        if not texts:
            return []

        payload = {
            "model": model,
            "input": texts,
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

        data_items = data.get("data")
        if not isinstance(data_items, list):
            raise ProviderError(
                provider=self.provider_name,
                message="Invalid embedding response format.",
                retryable=True,
                status_code=response.status_code,
            )
        usage_raw = data.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else None
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        results: list[EmbeddingResult] = []
        for item in data_items:
            if not isinstance(item, dict):
                continue
            raw_embedding = item.get("embedding")
            if not isinstance(raw_embedding, list):
                continue
            vector = _coerce_vector(raw_embedding)
            if not vector:
                continue
            results.append(
                EmbeddingResult(
                    provider=self.provider_name,
                    model=model,
                    embedding=vector,
                    dimensions=len(vector),
                    usage=usage,
                    latency_ms=latency_ms,
                )
            )
        if not results:
            raise ProviderError(
                provider=self.provider_name,
                message="Embedding provider returned empty vector list.",
                retryable=True,
                status_code=response.status_code,
            )
        return results


def _extract_embedding_vector(payload: dict[str, Any]) -> list[float]:
    data_items = payload.get("data")
    if isinstance(data_items, list) and data_items:
        first = data_items[0]
        if isinstance(first, dict):
            raw_embedding = first.get("embedding")
            if isinstance(raw_embedding, list):
                return _coerce_vector(raw_embedding)
    raw_embedding = payload.get("embedding")
    if isinstance(raw_embedding, list):
        return _coerce_vector(raw_embedding)
    return []


def _coerce_vector(values: list[Any]) -> list[float]:
    vector: list[float] = []
    for item in values:
        try:
            vector.append(float(item))
        except (TypeError, ValueError):
            return []
    return vector
