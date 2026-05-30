from __future__ import annotations

import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.storage.db import init_db
from app.storage.conversations import create_conversation, add_message
from app.core.orchestrator import ChatOrchestrator
from app.schemas.chat import (
    ChatChoice,
    ChatCompletionResponse,
    ChatMessage,
    GuardInfo,
    Usage,
)
from app.schemas.tools import ToolMetadata


@pytest.fixture
def temp_db(tmp_path) -> str:
    db_file = tmp_path / "test_conv_contract.db"
    db_path = str(db_file)
    init_db(db_path)
    return db_path


class MockOrchestratorForStore:
    async def create_chat_completion(self, request_id: str, request) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id="chatcmpl_store_test",
            object="chat.completion",
            created=1672531199,
            model=request.model,
            provider="groq",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Response for store!"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            guard=GuardInfo(),
            tools=ToolMetadata(),
            sources=[],
            model_alias=request.model,
        )


def test_conversation_store_contract(temp_db, monkeypatch) -> None:
    settings = Settings(
        app_env="development",
        diagnostics_enabled=True,
        require_api_key=False,
        rate_limit_enabled=False,
        nesty_db_path=temp_db,
        conversation_history_enabled=True,
    )
    monkeypatch.setattr("app.deps.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: MockOrchestratorForStore())

    app = create_app(settings)
    client = TestClient(app)

    payload = {
        "model": "nesty-combined-1.0",
        "messages": [{"role": "user", "content": "Hello store"}],
        "stream": False,
        "store": True,  # Enables storage
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Verify that conversation metadata is present in response
    assert "conversation" in data
    assert data["conversation"]["id"] is not None
    assert data["conversation"]["created"] is True
    assert data["conversation"]["summary_mode"] == "auto"


def test_conversation_list_detail_and_actions(temp_db, monkeypatch) -> None:
    settings = Settings(
        app_env="development",
        diagnostics_enabled=True,
        require_api_key=False,
        rate_limit_enabled=False,
        nesty_db_path=temp_db,
    )
    monkeypatch.setattr("app.deps.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)

    # Seed a conversation
    conv = create_conversation(api_key_id=None, title="Test Seed", db_path=temp_db)
    conv_id = conv["id"]
    add_message(conv_id, "user", "hi", db_path=temp_db)
    add_message(conv_id, "assistant", "hello", db_path=temp_db)

    app = create_app(settings)
    client = TestClient(app)

    # 1. Test GET /v1/conversations (list shape)
    response = client.get("/v1/conversations")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == conv_id
    assert data["data"][0]["title"] == "Test Seed"

    # 2. Test GET /v1/conversations/{id} (detail shape)
    response = client.get(f"/v1/conversations/{conv_id}")
    assert response.status_code == 200
    detail = response.json()
    assert "conversation" in detail
    assert "messages" in detail
    assert detail["conversation"]["id"] == conv_id
    assert len(detail["messages"]) == 2

    # 3. Test PATCH /v1/conversations/{id} (update title)
    response = client.patch(f"/v1/conversations/{conv_id}", json={"title": "Updated Seed"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # Verify title was updated
    response = client.get(f"/v1/conversations/{conv_id}")
    assert response.json()["conversation"]["title"] == "Updated Seed"

    # 4. Test GET /v1/conversations/{id}/messages
    response = client.get(f"/v1/conversations/{conv_id}/messages")
    assert response.status_code == 200
    msg_list = response.json()
    assert msg_list["object"] == "list"
    assert len(msg_list["data"]) == 2

    # 5. Test GET /v1/conversations/{id}/export
    response = client.get(f"/v1/conversations/{conv_id}/export")
    assert response.status_code == 200
    export_data = response.json()
    assert export_data["conversation"]["id"] == conv_id
    assert "messages" in export_data

    # 6. Test GET /v1/conversations/memory-controls
    response = client.get("/v1/conversations/memory-controls")
    assert response.status_code == 200
    mem = response.json()
    assert mem["object"] == "list"
    assert "data" in mem

    # 7. Test POST /v1/conversations/{id}/clear
    response = client.post(f"/v1/conversations/{conv_id}/clear", json={"keep_summary": False})
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # Verify messages are cleared
    response = client.get(f"/v1/conversations/{conv_id}")
    assert len(response.json()["messages"]) == 0
