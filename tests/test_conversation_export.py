from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import add_message, create_conversation, update_conversation_summary
from app.storage.db import init_db


def test_export_returns_sanitized_conversation_payload(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "conversation_export.db")
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
    conv = create_conversation(api_key_id=key["id"], title="export-me", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="hello", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="world", db_path=db_path)
    update_conversation_summary(conv["id"], "safe summary", 1, db_path=db_path)

    headers = {"Authorization": f"Bearer {raw_key}"}
    response = client.get(f"/v1/conversations/{conv['id']}/export", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "conversation" in payload
    assert "messages" in payload
    assert payload["summary"] == "safe summary"
    assert len(payload["messages"]) == 2
    assert payload["conversation"]["message_count"] == 2
    assert payload["conversation"]["summary_exists"] is True
    assert "api_key_id" not in payload["conversation"]
    assert "key_hash" not in payload["conversation"]
    assert "raw_key" not in payload["conversation"]


def test_export_not_found_for_missing_conversation(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "conversation_export_missing.db")
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
    _ = create_api_key_record(db_path, "owner", raw_key, hash_secret="secret123")
    headers = {"Authorization": f"Bearer {raw_key}"}
    response = client.get("/v1/conversations/conv_missing/export", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"
