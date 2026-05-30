from __future__ import annotations

from app.config import Settings
from app.schemas.chat import ChatChoice, ChatCompletionResponse, ChatMessage, GuardInfo, Usage
from app.schemas.tools import ToolMetadata
from app.storage.db import init_db


class _FakeOrchestrator:
    async def create_chat_completion(self, request_id: str, request):
        return ChatCompletionResponse(
            id="chatcmpl_embed_test",
            created=1700000000,
            model=request.model,
            provider="openrouter",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello from assistant"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            guard=GuardInfo(),
            tools=ToolMetadata(),
            sources=[],
        )

    async def create_chat_completion_stream(self, request_id: str, request):
        raise AssertionError("stream path not used in this test")


def test_chat_store_calls_message_embedding_when_enabled(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_embed_integration.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        embeddings_enabled=True,
        embeddings_store_message_embeddings=True,
    )
    fake = _FakeOrchestrator()
    embedded_messages: list[str] = []

    async def _mock_maybe_embed(message: dict, api_key_id: str | None):
        embedded_messages.append(str(message.get("id") or ""))
        return {"ok": True}

    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: fake)
    monkeypatch.setattr("app.api.chat.maybe_embed_conversation_message", _mock_maybe_embed)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "Hello there"}],
            "store": True,
            "search": "off",
        },
    )
    assert response.status_code == 200
    assert len(embedded_messages) == 2


def test_chat_succeeds_even_if_message_embedding_fails(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_embed_fail.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        embeddings_enabled=True,
        embeddings_store_message_embeddings=True,
    )
    fake = _FakeOrchestrator()

    async def _failing_embed(message: dict, api_key_id: str | None):
        raise RuntimeError("embedding failed")

    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: fake)
    monkeypatch.setattr("app.api.chat.maybe_embed_conversation_message", _failing_embed)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "Hello there"}],
            "store": True,
            "search": "off",
        },
    )
    assert response.status_code == 200
