from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import add_message, create_conversation
from app.storage.db import init_db
from app.storage.fts import is_fts5_available


def _setup(tmp_path):
    db_path = str(tmp_path / "conversation_search_fts.db")
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
    add_message(conversation_id=conv_a["id"], role="user", content="prepare budget forecast", db_path=db_path)
    add_message(conversation_id=conv_a["id"], role="assistant", content="forecast drafted", db_path=db_path)

    conv_b = create_conversation(api_key_id=key_b["id"], title="Private Notes", db_path=db_path)
    add_message(conversation_id=conv_b["id"], role="user", content="secret roadmap", db_path=db_path)

    return db_path, settings, raw_a, raw_b, conv_a["id"], conv_b["id"]


def test_search_auto_uses_fts_or_fallback_like(client, monkeypatch, tmp_path) -> None:
    db_path, settings, raw_a, _raw_b, _conv_a, _conv_b = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw_a}"}

    response = client.get("/v1/conversations/search?q=forecast&scope=messages&backend=auto", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["search"]["scope"] == "messages"
    assert len(payload["messages"]) >= 1

    if is_fts5_available(db_path):
        assert payload["search"]["backend"] == "fts"
        assert payload["search"]["fallback_used"] is False
        first = payload["messages"][0]
        assert first["search_backend"] == "fts"
        assert isinstance(first["rank"], (int, float))
        assert isinstance(first["snippet"], str)
    else:
        assert payload["search"]["backend"] == "like"
        assert payload["search"]["fallback_used"] is True
        first = payload["messages"][0]
        assert first["search_backend"] == "like"
        assert first["rank"] is None
        assert first["snippet"] is None


def test_search_messages_never_crosses_api_key_ownership(client, monkeypatch, tmp_path) -> None:
    _db_path, settings, raw_a, _raw_b, _conv_a, _conv_b = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw_a}"}

    response = client.get("/v1/conversations/search?q=roadmap&scope=messages&backend=auto", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"] == []


def test_clear_conversation_removes_messages_from_search(client, monkeypatch, tmp_path) -> None:
    _db_path, settings, raw_a, _raw_b, conv_a_id, _conv_b = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw_a}"}

    before = client.get("/v1/conversations/search?q=forecast&scope=messages&backend=auto", headers=headers)
    assert before.status_code == 200
    assert len(before.json()["messages"]) >= 1

    cleared = client.post(f"/v1/conversations/{conv_a_id}/clear", headers=headers, json={"keep_summary": False})
    assert cleared.status_code == 200
    assert cleared.json()["ok"] is True

    after = client.get("/v1/conversations/search?q=forecast&scope=messages&backend=auto", headers=headers)
    assert after.status_code == 200
    assert after.json()["messages"] == []
