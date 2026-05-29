from __future__ import annotations

from app.config import Settings
from app.schemas.chat import ChatChoice, ChatCompletionResponse, ChatMessage, GuardInfo, Usage
from app.schemas.tools import ToolMetadata
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import create_conversation
from app.storage.db import init_db


class _SimpleOrchestrator:
    async def create_chat_completion(self, request_id: str, request):
        return ChatCompletionResponse(
            id="chatcmpl_acl",
            created=1700000000,
            model=request.model,
            provider="openrouter",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="ok"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            guard=GuardInfo(),
            tools=ToolMetadata(),
            sources=[],
        )

    async def create_chat_completion_stream(self, request_id: str, request):
        raise AssertionError("stream path not needed here")


def test_api_key_a_cannot_access_api_key_b_conversation(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "acl_cross_key.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: _SimpleOrchestrator())
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    raw_a = generate_api_key("dev")
    key_a = create_api_key_record(db_path=db_path, name="A", raw_key=raw_a, hash_secret="secret123")
    raw_b = generate_api_key("dev")
    key_b = create_api_key_record(db_path=db_path, name="B", raw_key=raw_b, hash_secret="secret123")

    conv_b = create_conversation(api_key_id=key_b["id"], title="owned-by-b", db_path=db_path)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_a}"},
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv_b["id"],
            "messages": [{"role": "user", "content": "hello"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_dev_mode_can_use_null_api_key_conversation(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "acl_dev_mode.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: _SimpleOrchestrator())
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    conv = create_conversation(api_key_id=None, title="dev-conv", db_path=db_path)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv["id"],
            "messages": [{"role": "user", "content": "hello"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
