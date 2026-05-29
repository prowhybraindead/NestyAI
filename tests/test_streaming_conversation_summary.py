from __future__ import annotations

import json

from app.config import Settings
from app.core.orchestrator import StreamHandle, StreamOutcome
from app.schemas.chat import Usage
from app.schemas.tools import ToolMetadata
from app.storage.conversations import add_message, create_conversation, update_conversation_summary
from app.storage.db import init_db


class _SummaryStreamOrchestrator:
    def __init__(self) -> None:
        self.router = object()

    async def create_chat_completion(self, request_id: str, request):
        raise AssertionError("non-stream path not used")

    async def create_chat_completion_stream(self, request_id: str, request):
        async def events():
            yield (
                'data: {"id":"chatcmpl_stream_sum","object":"chat.completion.chunk","created":1700000000,'
                '"model":"nesty-combined-1.0","provider":"openrouter","choices":[{"index":0,'
                '"delta":{"content":"hello"},"finish_reason":null}]}\n\n'
            )
            metadata_payload = {
                "id": "chatcmpl_stream_sum",
                "object": "chat.completion.metadata",
                "created": 1700000000,
                "model": request.model,
                "provider": "openrouter",
                "guard": {"input_redacted": False, "output_redacted": False, "redaction_count": 0, "categories": []},
                "tools": {"used": [], "search": {"enabled": False, "query": None, "results_count": 0, "failed": False}, "executions": []},
                "sources": [],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "conversation": {
                    "id": request.conversation_id,
                    "created": request.conversation_created,
                    "summary_used": request.conversation_summary_used,
                    "summary_updated": request.conversation_summary_updated,
                },
            }
            yield f"data: {json.dumps(metadata_payload, separators=(',', ':'))}\n\n"
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
                conversation_summary_used=request.conversation_summary_used,
                conversation_summary_updated=request.conversation_summary_updated,
            ),
        )


def _extract_data_events(payload: str) -> list[dict]:
    events: list[dict] = []
    for raw in payload.splitlines():
        line = raw.strip()
        if not line.startswith("data: "):
            continue
        value = line[6:]
        if value == "[DONE]":
            continue
        events.append(json.loads(value))
    return events


def test_stream_metadata_contains_summary_flags(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "stream_summary_metadata.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_summary_enabled=True,
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: _SummaryStreamOrchestrator())
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    conv = create_conversation(api_key_id=None, title="stream sum", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="old", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="old2", db_path=db_path)
    update_conversation_summary(
        conversation_id=conv["id"],
        summary="conversation summary content",
        summary_message_count=1,
        db_path=db_path,
    )

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "nesty-combined-1.0",
            "conversation_id": conv["id"],
            "messages": [{"role": "user", "content": "next"}],
            "stream": True,
            "store": True,
            "search": "off",
            "tools": "off",
        },
    ) as response:
        payload = "".join(response.iter_text())

    assert response.status_code == 200
    assert "data: [DONE]" in payload
    events = _extract_data_events(payload)
    metadata = next(event for event in events if event.get("object") == "chat.completion.metadata")
    assert metadata["conversation"]["summary_used"] is True


def test_stream_summary_failure_does_not_break_stream(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "stream_summary_failure.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        require_api_key=False,
        rate_limit_enabled=False,
        conversation_summary_enabled=True,
        conversation_summary_trigger_messages=2,
        conversation_summary_keep_recent_messages=1,
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: _SummaryStreamOrchestrator())
    monkeypatch.setattr("app.api.chat.get_guard_rules", lambda: {})

    async def _raise_summary(*args, **kwargs):
        raise RuntimeError("summary failed")

    monkeypatch.setattr("app.api.chat.summarize_conversation", _raise_summary)

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
