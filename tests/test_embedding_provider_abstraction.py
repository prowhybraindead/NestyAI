from __future__ import annotations

import pytest

from app.core.errors import APIError, ProviderError
from app.embeddings.openrouter import OpenRouterEmbeddingProvider
from app.embeddings.provider import NoOpEmbeddingProvider, build_embedding_provider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, json, headers):
        return self._response


@pytest.mark.asyncio
async def test_openrouter_embedding_provider_parses_valid_response(monkeypatch) -> None:
    payload = {
        "data": [{"embedding": [0.1, 0.2, 0.3]}],
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }
    monkeypatch.setattr(
        "app.embeddings.openrouter.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(_FakeResponse(status_code=200, payload=payload)),
    )
    provider = OpenRouterEmbeddingProvider(api_key="test", timeout_seconds=5)
    result = await provider.embed_text("hello", model="embed-model")
    assert result.provider == "openrouter"
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.dimensions == 3


@pytest.mark.asyncio
async def test_openrouter_embedding_provider_unavailable_raises_provider_error(monkeypatch) -> None:
    payload = {"error": {"message": "temporary"}}
    monkeypatch.setattr(
        "app.embeddings.openrouter.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(_FakeResponse(status_code=503, payload=payload)),
    )
    provider = OpenRouterEmbeddingProvider(api_key="test", timeout_seconds=5)
    with pytest.raises(ProviderError):
        await provider.embed_text("hello", model="embed-model")


def test_build_embedding_provider_invalid_provider_rejected() -> None:
    settings = type(
        "S",
        (),
        {
            "embeddings_provider": "invalid",
            "openrouter_api_key": None,
            "nvidia_api_key": None,
            "nvidia_base_url": None,
            "embeddings_timeout_seconds": 30,
        },
    )()
    with pytest.raises(APIError) as exc_info:
        build_embedding_provider(settings=settings)
    assert exc_info.value.code == "embedding_config_invalid"


@pytest.mark.asyncio
async def test_noop_embedding_provider_is_deterministic() -> None:
    provider = NoOpEmbeddingProvider()
    first = await provider.embed_text("hello world", model="noop-embedding")
    second = await provider.embed_text("hello world", model="noop-embedding")
    assert first.embedding == second.embedding
    assert first.dimensions == len(first.embedding)
