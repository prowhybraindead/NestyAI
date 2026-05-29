from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.core.conversation_summarizer import build_summary_prompt, should_summarize, summarize_conversation
from app.schemas.provider import ProviderChatResult
from app.storage.conversations import add_message, create_conversation, get_conversation, get_conversation_summary
from app.storage.db import init_db


class _FakeRouter:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    async def route_chat(self, request_id: str, model_alias: str, messages, temperature: float, max_tokens: int):
        self.calls.append(
            {
                "request_id": request_id,
                "model_alias": model_alias,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return SimpleNamespace(provider_result=ProviderChatResult(provider="openrouter", content=self.content))


def test_should_summarize_respects_threshold() -> None:
    config = Settings(
        conversation_summary_enabled=True,
        conversation_summary_trigger_messages=6,
        conversation_summary_keep_recent_messages=2,
    )
    conversation = {"archived_at": None, "summary_message_count": 0}
    assert should_summarize(conversation, total_message_count=5, config=config) is False
    assert should_summarize(conversation, total_message_count=6, config=config) is True


def test_build_summary_prompt_includes_existing_summary_and_messages() -> None:
    prompt = build_summary_prompt(
        existing_summary="older summary",
        older_messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ],
    )
    assert len(prompt) == 2
    assert "older summary" in prompt[1]["content"]
    assert "user: hello" in prompt[1]["content"]
    assert "assistant: world" in prompt[1]["content"]


@pytest.mark.asyncio
async def test_summarize_conversation_updates_summary_and_enforces_max_chars(tmp_path) -> None:
    db_path = str(tmp_path / "summarizer.db")
    init_db(db_path)
    config = Settings(
        nesty_db_path=db_path,
        conversation_summary_enabled=True,
        conversation_summary_trigger_messages=4,
        conversation_summary_keep_recent_messages=2,
        conversation_summary_max_chars=28,
        conversation_summary_model="nesty-flash-1.0",
    )
    router = _FakeRouter(content="token=abcd sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 long summary body")

    conv = create_conversation(api_key_id=None, title="sum", db_path=db_path)
    conv_id = conv["id"]
    add_message(conversation_id=conv_id, role="user", content="u1", db_path=db_path)
    add_message(conversation_id=conv_id, role="assistant", content="a1", db_path=db_path)
    add_message(conversation_id=conv_id, role="user", content="u2", db_path=db_path)
    add_message(conversation_id=conv_id, role="assistant", content="a2", db_path=db_path)
    add_message(conversation_id=conv_id, role="user", content="u3", db_path=db_path)

    summary = await summarize_conversation(conversation_id=conv_id, router=router, config=config)
    assert summary is not None
    assert len(summary) <= 28
    assert "sk-" not in summary

    saved = get_conversation_summary(conv_id, db_path=db_path)
    assert saved is not None
    assert saved["summary"] == summary
    assert saved["summary_message_count"] == 3
    assert saved["summary_updated_at"] is not None

    full_conv = get_conversation(conv_id, db_path=db_path)
    assert full_conv is not None
    assert full_conv["summary_message_count"] == 3
    assert router.calls[0]["model_alias"] == "nesty-flash-1.0"
