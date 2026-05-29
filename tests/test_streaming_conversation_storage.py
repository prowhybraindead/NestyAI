from __future__ import annotations

from app.config import Settings
from app.core.orchestrator import StreamHandle, StreamOutcome
from app.schemas.chat import Usage
from app.schemas.tools import ToolMetadata
from app.storage.conversations import get_recent_messages
from app.storage.db import init_db


class _StreamSuccessOrchestrator:
    async def create_chat_completion(self, request_id: str, request):
        raise AssertionError("non-stream path not used")

    async def create_chat_completion_stream(self, request_id: str, request):
        async def events():
            yield (
                'data: {"id":"chatcmpl_stream","object":"chat.completion.chunk","created":1700000000,'
                '"model":"nesty-combined-1.0","provider":"openrouter","choices":[{"index":0,'
                '"delta":{"role":"assistant"},"finish_reason":null}]}\n\n'
            )
            yield "data: [DONE]\n\n"

        return StreamHandle(
            events=events(),
            outcome=StreamOutcome(
                provider="openrouter",
                usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                tools=ToolMetadata(),
                status="success",
                assistant_content="safe assistant",
                conversation_id=request.conversation_id,
                conversation_created=request.conversation_created,
            ),
        )


class _StreamErrorOrchestrator:
    async def create_chat_completion(self, request_id: str, request):
        raise AssertionError("non-stream path not used")

    async def create_chat_completion_stream(self, request_id: str, request):
        async def events():
            yield (
                'data: {"object":"chat.completion.error","error":{"code":"stream_interrupted","message":"x"}}\n\n'
            )
            yield "data: [DONE]\n\n"

        return StreamHandle(
            events=events(),
            outcome=StreamOutcome(
                provider="openrouter",
                usage=Usage(),
                tools=ToolMetadata(),
                status="error",
                error_code="stream_interrupted",
                assistant_content="",
                conversation_id=request.conversation_id,
                conversation_created=request.conversation_created,
            ),
        )


def test_stream_store_true_saves_user_and_assistant(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "stream_conv_success.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: _StreamSuccessOrchestrator())
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "hello stream"}],
            "stream": True,
            "store": True,
            "search": "off",
            "tools": "off",
        },
    ) as response:
        payload = "".join(response.iter_text())

    assert response.status_code == 200
    assert "data: [DONE]" in payload

    conv_id = None
    for line in payload.splitlines():
        if '"object":"chat.completion.metadata"' in line or '"object": "chat.completion.metadata"' in line:
            # metadata may be absent in mocked stream; fallback below.
            pass
    # conversation id is not required in mocked payload for this test; find created row.
    # There should be exactly one conversation with two messages.
    from app.storage.conversations import list_conversations

    convs = list_conversations(api_key_id=None, db_path=db_path)
    assert len(convs) == 1
    conv_id = convs[0]["id"]
    messages = get_recent_messages(conv_id, limit=20, db_path=db_path)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "safe assistant"


def test_stream_error_does_not_store_assistant_message(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "stream_conv_error.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: _StreamErrorOrchestrator())
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "messages": [{"role": "user", "content": "hello stream"}],
            "stream": True,
            "store": True,
            "search": "off",
            "tools": "off",
        },
    ) as response:
        _ = "".join(response.iter_text())

    assert response.status_code == 200
    from app.storage.conversations import list_conversations

    convs = list_conversations(api_key_id=None, db_path=db_path)
    assert len(convs) == 1
    conv_id = convs[0]["id"]
    messages = get_recent_messages(conv_id, limit=20, db_path=db_path)
    assert [m["role"] for m in messages] == ["user"]
