from __future__ import annotations

from app.config import Settings
from app.schemas.chat import ChatChoice, ChatCompletionResponse, ChatMessage, GuardInfo, Usage
from app.schemas.tools import ToolMetadata
from app.storage.conversations import add_message, create_conversation, list_conversations
from app.storage.db import init_db


class _ConversationAwareOrchestrator:
    def __init__(self) -> None:
        self.captured_message_counts: list[int] = []
        self.captured_messages: list[list[ChatMessage]] = []

    async def create_chat_completion(self, request_id: str, request):
        self.captured_message_counts.append(len(request.messages))
        self.captured_messages.append(request.messages)
        return ChatCompletionResponse(
            id="chatcmpl_conv",
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
            usage=Usage(prompt_tokens=2, completion_tokens=2, total_tokens=4),
            guard=GuardInfo(),
            tools=ToolMetadata(),
            sources=[],
        )

    async def create_chat_completion_stream(self, request_id: str, request):
        raise AssertionError("stream path not used in this test")


def test_store_false_does_not_create_conversation(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_store_false.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    orch = _ConversationAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "hello"}],
            "store": False,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "conversation" not in payload
    assert list_conversations(api_key_id=None, db_path=db_path) == []


def test_store_true_creates_conversation_and_returns_id(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_store_true.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    orch = _ConversationAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "first msg"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["id"].startswith("conv_")
    assert payload["conversation"]["created"] is True


def test_conversation_id_loads_history_when_store_true(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_history.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_history_enabled=True,
        conversation_history_max_messages=20,
        conversation_history_max_chars=12000,
    )
    orch = _ConversationAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    start = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "hello one"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    conv_id = start.json()["conversation"]["id"]

    follow = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "hello two"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert follow.status_code == 200
    assert orch.captured_message_counts[-1] >= 2


def test_invalid_conversation_id_returns_not_found(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_invalid_conv.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    orch = _ConversationAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": "conv_missing",
            "messages": [{"role": "user", "content": "hello"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_history_respects_max_messages_and_chars(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_history_limits.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_history_enabled=True,
        conversation_history_max_messages=2,
        conversation_history_max_chars=8,
    )
    orch = _ConversationAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    conv = create_conversation(api_key_id=None, title="limits", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="abcdef", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="ghijkl", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="mnopqr", db_path=db_path)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv["id"],
            "messages": [{"role": "user", "content": "new"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    # with tight char budget, at most one short history message is included before current message
    assert orch.captured_message_counts[-1] <= 2
