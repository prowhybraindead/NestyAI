from __future__ import annotations

from app.config import Settings
from app.schemas.chat import ChatChoice, ChatCompletionResponse, ChatMessage, GuardInfo, Usage
from app.schemas.tools import ToolMetadata
from app.storage.conversations import add_message, create_conversation, update_conversation_summary
from app.storage.db import init_db


class _ModeOrchestrator:
    def __init__(self) -> None:
        self.router = object()
        self.captured_messages: list[list[ChatMessage]] = []

    async def create_chat_completion(self, request_id: str, request):
        self.captured_messages.append(request.messages)
        return ChatCompletionResponse(
            id="chatcmpl_mode",
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
        raise AssertionError("stream path not used")


def test_summary_off_disables_summary_injection(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "summary_mode_off.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_summary_enabled=True,
    )
    orchestrator = _ModeOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orchestrator)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})
    called = {"value": False}

    async def _fake_summary(*args, **kwargs):
        called["value"] = True
        return "x"

    monkeypatch.setattr("app.api.chat.summarize_conversation", _fake_summary)

    conv = create_conversation(api_key_id=None, title="sum-off", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="u1", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="a1", db_path=db_path)
    update_conversation_summary(conv["id"], "summary here", 2, db_path=db_path)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv["id"],
            "messages": [{"role": "user", "content": "next"}],
            "store": True,
            "summary": "off",
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["summary_mode"] == "off"
    assert payload["conversation"]["summary_used"] is False
    assert payload["conversation"]["summary_updated"] is False
    assert called["value"] is False
    captured = orchestrator.captured_messages[-1]
    assert not any(m.role == "system" and "Conversation summary so far" in m.content for m in captured)


def test_summary_force_triggers_summarization_below_threshold(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "summary_mode_force.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_summary_enabled=True,
        conversation_summary_trigger_messages=100,
        conversation_summary_keep_recent_messages=12,
    )
    orchestrator = _ModeOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orchestrator)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    called = {"value": False}

    async def _fake_summary(*args, **kwargs):
        called["value"] = kwargs.get("force") is True
        return "forced-summary"

    monkeypatch.setattr("app.api.chat.summarize_conversation", _fake_summary)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "hello force"}],
            "store": True,
            "summary": "force",
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["summary_mode"] == "force"
    assert payload["conversation"]["summary_updated"] is True
    assert called["value"] is True


def test_invalid_summary_mode_returns_error(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "summary_mode_invalid.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: _ModeOrchestrator())

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "hello"}],
            "store": True,
            "summary": "invalid-value",
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_conversation_request"
