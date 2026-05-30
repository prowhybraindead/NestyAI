from __future__ import annotations

import pytest

from app.core.embedding_service import (
    generate_and_store_embedding,
    generate_embedding,
    hash_embedding_content,
    maybe_embed_conversation_message,
    normalize_embedding_text,
)
from app.core.errors import APIError
from app.schemas.embeddings import EmbeddingResult
from app.storage.db import init_db
from app.storage.embeddings import count_embedding_records


class _DummyEmbeddingProvider:
    provider_name = "noop"

    def __init__(self) -> None:
        self.calls = 0

    async def embed_text(self, text: str, model: str) -> EmbeddingResult:
        self.calls += 1
        return EmbeddingResult(
            provider="noop",
            model=model,
            embedding=[0.1, 0.2, 0.3],
            dimensions=3,
            usage={"total_tokens": 1},
            latency_ms=1,
        )


def test_hash_embedding_content_is_deterministic() -> None:
    assert hash_embedding_content("hello") == hash_embedding_content("hello")
    assert hash_embedding_content("hello") != hash_embedding_content("hello!")


def test_normalize_embedding_text_respects_max_chars() -> None:
    text = "  Hello   world  \n\n and   team  "
    normalized = normalize_embedding_text(text, max_chars=11)
    assert normalized == "Hello world"


@pytest.mark.asyncio
async def test_generate_embedding_with_mocked_provider(monkeypatch) -> None:
    provider = _DummyEmbeddingProvider()
    monkeypatch.setattr(
        "app.core.embedding_service.get_settings",
        lambda: type(
            "S",
            (),
            {
                "embeddings_provider": "noop",
                "embeddings_model": "test-embed-model",
                "embeddings_max_input_chars": 8000,
            },
        )(),
    )
    monkeypatch.setattr("app.core.embedding_service.build_embedding_provider", lambda settings, provider_name: provider)

    result = await generate_embedding("hello world")
    assert result.provider == "noop"
    assert result.dimensions == 3
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_generate_and_store_embedding_disabled_returns_none_and_does_not_call_provider(monkeypatch) -> None:
    provider = _DummyEmbeddingProvider()
    monkeypatch.setattr(
        "app.core.embedding_service.get_settings",
        lambda: type(
            "S",
            (),
            {
                "embeddings_enabled": False,
                "embeddings_provider": "noop",
                "embeddings_model": "test-embed-model",
                "embeddings_max_input_chars": 8000,
                "nesty_db_path": "unused.db",
            },
        )(),
    )
    monkeypatch.setattr("app.core.embedding_service.build_embedding_provider", lambda settings, provider_name: provider)

    saved = await generate_and_store_embedding(
        owner_type="conversation_message",
        owner_id="msg_1",
        api_key_id=None,
        text="hello",
    )
    assert saved is None
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_maybe_embed_conversation_message_best_effort(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "embedding_service_best_effort.db")
    init_db(db_path)
    provider = _DummyEmbeddingProvider()
    monkeypatch.setattr(
        "app.core.embedding_service.get_settings",
        lambda: type(
            "S",
            (),
            {
                "embeddings_enabled": True,
                "embeddings_store_message_embeddings": True,
                "embeddings_provider": "noop",
                "embeddings_model": "test-embed-model",
                "embeddings_max_input_chars": 8000,
                "nesty_db_path": db_path,
            },
        )(),
    )
    monkeypatch.setattr("app.core.embedding_service.build_embedding_provider", lambda settings, provider_name: provider)
    monkeypatch.setattr("app.storage.embeddings.get_settings", lambda: type("S", (), {"nesty_db_path": db_path})())

    saved = await maybe_embed_conversation_message(
        message={"id": "msg_1", "conversation_id": "conv_1", "role": "user", "content": "hello"},
        api_key_id="key_1",
    )
    assert saved is not None
    assert provider.calls == 1
    assert count_embedding_records(db_path=db_path) == 1


@pytest.mark.asyncio
async def test_generate_and_store_embedding_provider_unavailable_returns_none(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "embedding_service_provider_fail.db")
    init_db(db_path)

    async def _raise(*args, **kwargs):
        raise APIError(code="embedding_provider_unavailable", message="x", status_code=503)

    monkeypatch.setattr(
        "app.core.embedding_service.get_settings",
        lambda: type(
            "S",
            (),
            {
                "embeddings_enabled": True,
                "embeddings_provider": "noop",
                "embeddings_model": "test-embed-model",
                "embeddings_max_input_chars": 8000,
                "nesty_db_path": db_path,
            },
        )(),
    )
    monkeypatch.setattr("app.core.embedding_service.generate_embedding", _raise)

    saved = await generate_and_store_embedding(
        owner_type="conversation_message",
        owner_id="msg_1",
        api_key_id="key_1",
        text="hello",
    )
    assert saved is None
