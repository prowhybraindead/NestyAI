from __future__ import annotations

import sqlite3

from app.storage.conversations import (
    add_message,
    create_conversation,
    get_conversation_summary,
    get_message_count,
    get_messages_after_summary,
    update_conversation_summary,
)
from app.storage.db import init_db


def test_db_migration_adds_summary_columns(tmp_path) -> None:
    db_path = str(tmp_path / "summary_columns.db")
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}

    assert "summary" in columns
    assert "summary_updated_at" in columns
    assert "summary_message_count" in columns


def test_summary_storage_and_messages_after_summary(tmp_path) -> None:
    db_path = str(tmp_path / "summary_storage.db")
    init_db(db_path)

    conv = create_conversation(api_key_id=None, title="summary test", db_path=db_path)
    conv_id = conv["id"]

    add_message(conversation_id=conv_id, role="user", content="u1", db_path=db_path)
    add_message(conversation_id=conv_id, role="assistant", content="a1", db_path=db_path)
    add_message(conversation_id=conv_id, role="user", content="u2", db_path=db_path)
    add_message(conversation_id=conv_id, role="assistant", content="a2", db_path=db_path)

    assert get_message_count(conv_id, db_path=db_path) == 4
    assert update_conversation_summary(conv_id, "compressed summary", 2, db_path=db_path) is True

    summary = get_conversation_summary(conv_id, db_path=db_path)
    assert summary is not None
    assert summary["summary"] == "compressed summary"
    assert summary["summary_message_count"] == 2
    assert summary["summary_updated_at"] is not None

    tail = get_messages_after_summary(conv_id, summary_message_count=2, limit=20, db_path=db_path)
    assert [item["content"] for item in tail] == ["u2", "a2"]
