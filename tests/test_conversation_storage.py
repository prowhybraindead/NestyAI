from __future__ import annotations

from app.storage.conversations import (
    add_message,
    archive_conversation,
    count_messages,
    create_conversation,
    get_recent_messages,
    list_conversations,
    update_conversation_title,
)
from app.storage.db import init_db


def test_conversation_storage_crud(tmp_path) -> None:
    db_path = str(tmp_path / "conv_storage.db")
    init_db(db_path)

    conv = create_conversation(api_key_id="key_a", title="hello", db_path=db_path)
    conv_id = conv["id"]
    assert conv_id.startswith("conv_")

    add_message(conversation_id=conv_id, role="user", content="u1", model="nesty-combined-1.0", db_path=db_path)
    add_message(conversation_id=conv_id, role="assistant", content="a1", provider="openrouter", db_path=db_path)

    recent = get_recent_messages(conv_id, limit=20, db_path=db_path)
    assert len(recent) == 2
    assert recent[0]["role"] == "user"
    assert recent[1]["role"] == "assistant"

    items = list_conversations(api_key_id="key_a", limit=20, offset=0, db_path=db_path)
    assert len(items) == 1
    assert items[0]["id"] == conv_id

    assert count_messages(conv_id, db_path=db_path) == 2

    assert update_conversation_title(conv_id, "updated", api_key_id="key_a", db_path=db_path) is True
    assert archive_conversation(conv_id, api_key_id="key_a", db_path=db_path) is True
    items_after_archive = list_conversations(api_key_id="key_a", limit=20, offset=0, db_path=db_path)
    assert items_after_archive == []
