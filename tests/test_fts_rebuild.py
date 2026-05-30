from __future__ import annotations

from app.storage.conversations import add_message, create_conversation
from app.storage.db import get_connection, init_db
from app.storage.fts import is_fts5_available, rebuild_conversation_fts


def test_rebuild_fts_indexes_existing_messages(tmp_path) -> None:
    db_path = str(tmp_path / "fts_rebuild.db")
    init_db(db_path)
    conv = create_conversation(api_key_id=None, title="search", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="first note", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="second note", db_path=db_path)

    result = rebuild_conversation_fts(db_path)
    assert isinstance(result, dict)
    assert isinstance(result.get("fts_available"), bool)
    assert isinstance(int(result.get("indexed_messages") or 0), int)

    if not is_fts5_available(db_path):
        assert result["ok"] is False
        assert result["error_code"] == "fts_unavailable"
        return

    assert result["ok"] is True
    assert int(result["indexed_messages"]) >= 2
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM conversation_messages_fts").fetchone()
    assert int(row["total"] or 0) == 2
