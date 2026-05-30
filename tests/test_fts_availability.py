from __future__ import annotations

from app.storage.conversations import add_message, create_conversation
from app.storage.db import get_connection, init_db
from app.storage.fts import init_conversation_fts, is_fts5_available


def test_fts5_availability_returns_bool(tmp_path) -> None:
    db_path = str(tmp_path / "fts_availability.db")
    init_db(db_path)
    available = is_fts5_available(db_path)
    assert isinstance(available, bool)


def test_init_fts_does_not_break_database(tmp_path) -> None:
    db_path = str(tmp_path / "fts_init_safe.db")
    init_db(db_path)
    fts_enabled = init_conversation_fts(db_path)
    assert isinstance(fts_enabled, bool)

    conv = create_conversation(api_key_id=None, title="safe", db_path=db_path)
    message = add_message(conversation_id=conv["id"], role="user", content="hello", db_path=db_path)
    assert message["id"].startswith("msg_")

    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM conversation_messages").fetchone()
    assert int(row["total"] or 0) == 1
