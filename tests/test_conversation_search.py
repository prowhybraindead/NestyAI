from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import add_message, create_conversation
from app.storage.db import init_db


def _setup(tmp_path):
    db_path = str(tmp_path / "conversation_search.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
    )
    raw_a = generate_api_key("dev")
    raw_b = generate_api_key("dev")
    key_a = create_api_key_record(db_path, "key-a", raw_a, hash_secret="secret123")
    key_b = create_api_key_record(db_path, "key-b", raw_b, hash_secret="secret123")

    conv_a = create_conversation(api_key_id=key_a["id"], title="Budget Planning", db_path=db_path)
    add_message(conversation_id=conv_a["id"], role="user", content="Prepare budget forecast", db_path=db_path)
    add_message(conversation_id=conv_a["id"], role="assistant", content="Budget draft ready", db_path=db_path)

    conv_b = create_conversation(api_key_id=key_b["id"], title="Private Notes", db_path=db_path)
    add_message(conversation_id=conv_b["id"], role="user", content="secret roadmap", db_path=db_path)

    return db_path, settings, raw_a, raw_b, conv_a["id"], conv_b["id"]


def test_search_conversations_and_messages(client, monkeypatch, tmp_path) -> None:
    _db, settings, raw_a, _raw_b, conv_a_id, _conv_b_id = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw_a}"}

    by_title = client.get("/v1/conversations/search?q=Budget&scope=conversations", headers=headers)
    assert by_title.status_code == 200
    payload = by_title.json()
    assert payload["conversations"][0]["id"] == conv_a_id
    assert payload["messages"] == []

    by_message = client.get("/v1/conversations/search?q=forecast&scope=messages", headers=headers)
    assert by_message.status_code == 200
    msg_payload = by_message.json()
    assert len(msg_payload["messages"]) >= 1
    assert any("forecast" in item["content"] for item in msg_payload["messages"])


def test_search_does_not_cross_api_key_ownership(client, monkeypatch, tmp_path) -> None:
    _db, settings, raw_a, _raw_b, _conv_a_id, _conv_b_id = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers_a = {"Authorization": f"Bearer {raw_a}"}

    response = client.get("/v1/conversations/search?q=roadmap&scope=all", headers=headers_a)
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversations"] == []
    assert payload["messages"] == []


def test_search_invalid_scope_archived_q(client, monkeypatch, tmp_path) -> None:
    _db, settings, raw_a, _raw_b, conv_a_id, _conv_b_id = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw_a}"}

    bad_scope = client.get("/v1/conversations/search?q=abc&scope=weird", headers=headers)
    assert bad_scope.status_code == 400
    assert bad_scope.json()["error"]["code"] == "invalid_conversation_request"

    empty_q = client.get("/v1/conversations/search?q=   &scope=all", headers=headers)
    assert empty_q.status_code == 400
    assert empty_q.json()["error"]["code"] == "invalid_conversation_request"

    bad_archived = client.get("/v1/conversations?archived=invalid", headers=headers)
    assert bad_archived.status_code == 400
    assert bad_archived.json()["error"]["code"] == "invalid_conversation_request"

    # sanity: valid call still works
    ok = client.get(f"/v1/conversations/{conv_a_id}/messages?limit=20&offset=0&order=asc", headers=headers)
    assert ok.status_code == 200
