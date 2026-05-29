from __future__ import annotations

from app.config import Settings
from app.schemas.chat import ChatChoice, ChatCompletionResponse, ChatMessage, GuardInfo, Usage
from app.schemas.tools import ToolMetadata
from app.storage.conversations import add_message, create_conversation, update_conversation_summary
from app.storage.db import init_db


class _SummaryAwareOrchestrator:
    def __init__(self) -> None:
        self.router = object()
        self.captured_messages: list[list[ChatMessage]] = []

    async def create_chat_completion(self, request_id: str, request):
        self.captured_messages.append(request.messages)
        return ChatCompletionResponse(
            id="chatcmpl_summary",
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
        raise AssertionError("stream not used")


def test_chat_injects_summary_when_available(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_summary_injection.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_history_enabled=True,
        conversation_history_max_messages=10,
        conversation_history_max_chars=4000,
        conversation_summary_enabled=True,
    )
    orch = _SummaryAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})
    monkeypatch.setattr("app.api.chat.summarize_conversation", lambda *args, **kwargs: None)

    conv = create_conversation(api_key_id=None, title="sum", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="old user", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="old assistant", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="recent user", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="recent assistant", db_path=db_path)
    update_conversation_summary(
        conversation_id=conv["id"],
        summary="user likes concise bullet points",
        summary_message_count=2,
        db_path=db_path,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv["id"],
            "messages": [{"role": "user", "content": "new question"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["summary_used"] is True

    captured = orch.captured_messages[-1]
    assert any(m.role == "system" and "Conversation summary so far" in m.content for m in captured)
    joined = "\n".join(m.content for m in captured)
    assert "old user" not in joined
    assert "old assistant" not in joined


def test_chat_falls_back_to_recent_window_when_summary_missing(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_summary_fallback.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_history_enabled=True,
        conversation_summary_enabled=True,
    )
    orch = _SummaryAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})
    monkeypatch.setattr("app.api.chat.summarize_conversation", lambda *args, **kwargs: None)

    conv = create_conversation(api_key_id=None, title="fallback", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="hello there", db_path=db_path)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv["id"],
            "messages": [{"role": "user", "content": "next"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["summary_used"] is False
    assert payload["conversation"]["summary_updated"] is False

    captured = orch.captured_messages[-1]
    assert not any(m.role == "system" and "Conversation summary so far" in m.content for m in captured)


def test_summarization_failure_does_not_fail_chat(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "chat_summary_failure.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_summary_enabled=True,
        conversation_summary_trigger_messages=2,
        conversation_summary_keep_recent_messages=1,
    )
    orch = _SummaryAwareOrchestrator()
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orch)
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    async def _raise_summary(*args, **kwargs):
        raise RuntimeError("summary failed")

    monkeypatch.setattr("app.api.chat.summarize_conversation", _raise_summary)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "please remember this"}],
            "store": True,
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["summary_updated"] is False
