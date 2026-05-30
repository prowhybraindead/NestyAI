from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.core.orchestrator import ChatOrchestrator
from app.schemas.chat import (
    ChatChoice,
    ChatCompletionResponse,
    ChatMessage,
    GuardInfo,
    Usage,
    OrchestrationInfo,
    SemanticRecallInfo,
    ProviderHealthInfo,
)
from app.schemas.tools import ToolMetadata


class MockChatOrchestrator:
    async def create_chat_completion(self, request_id: str, request) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id="chatcmpl_test_123",
            object="chat.completion",
            created=1672531199,
            model=request.model,
            provider="groq",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello, Nesty!"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            guard=GuardInfo(input_redacted=False, output_redacted=False, redaction_count=0),
            tools=ToolMetadata(),
            sources=[],
            orchestration=OrchestrationInfo(enabled=False, requested="auto", used=False),
            semantic_recall=SemanticRecallInfo(enabled=False, requested="auto", used=False),
            provider_health=None,
            model_alias=request.model,
        )


def test_non_stream_chat_completion_contract(monkeypatch) -> None:
    settings = Settings(
        app_env="development",
        diagnostics_enabled=True,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.deps.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: MockChatOrchestrator())

    app = create_app(settings)
    client = TestClient(app)

    payload = {
        "model": "nesty-combined-1.0",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
        "store": False,
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Core OpenAI Fields
    assert data["id"] == "chatcmpl_test_123"
    assert data["object"] == "chat.completion"
    assert data["created"] == 1672531199
    assert data["model"] == "nesty-combined-1.0"
    assert isinstance(data["choices"], list)
    assert len(data["choices"]) == 1
    assert data["choices"][0]["index"] == 0
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "Hello, Nesty!"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"]["prompt_tokens"] == 5
    assert data["usage"]["completion_tokens"] == 5
    assert data["usage"]["total_tokens"] == 10

    # Additive Nesty Metadata Fields
    assert "guard" in data
    assert "tools" in data
    assert "sources" in data
    assert "orchestration" in data
    assert "semantic_recall" in data
    assert data["provider"] == "groq"
    assert data["model_alias"] == "nesty-combined-1.0"
