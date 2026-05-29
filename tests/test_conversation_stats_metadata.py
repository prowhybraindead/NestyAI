from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import add_message, create_conversation, update_conversation_summary
from app.storage.db import init_db


def test_conversation_list_and_detail_include_stats_metadata(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "conversation_stats.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)

    raw_key = generate_api_key("dev")
    key = create_api_key_record(db_path, "owner", raw_key, hash_secret="secret123")
    conv = create_conversation(api_key_id=key["id"], title="stats", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="u1", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="a1", db_path=db_path)
    update_conversation_summary(conv["id"], "summary text", 1, db_path=db_path)

    headers = {"Authorization": f"Bearer {raw_key}"}

    list_resp = client.get("/v1/conversations?limit=20&offset=0", headers=headers)
    assert list_resp.status_code == 200
    list_items = list_resp.json()["data"]
    item = next(row for row in list_items if row["id"] == conv["id"])
    assert item["message_count"] == 2
    assert item["last_message_at"] is not None
    assert item["summary_exists"] is True
    assert item["summary_message_count"] == 1
    assert "archived_at" in item

    detail_resp = client.get(f"/v1/conversations/{conv['id']}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["conversation"]
    assert detail["message_count"] == 2
    assert detail["last_message_at"] is not None
    assert detail["summary_exists"] is True
    assert detail["summary"] == "summary text"
    assert detail["summary_message_count"] == 1
    assert "archived_at" in detail
