from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import add_message, create_conversation
from app.storage.db import init_db
from app.storage.fts import is_fts5_available


def _setup(tmp_path):
    db_path = str(tmp_path / "conversation_search_backend_modes.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
    )
    raw = generate_api_key("dev")
    key = create_api_key_record(db_path, "key-a", raw, hash_secret="secret123")
    conv = create_conversation(api_key_id=key["id"], title="Team backlog", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="release plan", db_path=db_path)
    return db_path, settings, raw


def test_backend_like_forces_like_search(client, monkeypatch, tmp_path) -> None:
    _db_path, settings, raw = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get("/v1/conversations/search?q=release&scope=messages&backend=like", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["search"]["backend"] == "like"
    assert payload["search"]["fallback_used"] is False
    assert all(item["search_backend"] == "like" for item in payload["messages"])


def test_backend_fts_mode_or_unavailable_error(client, monkeypatch, tmp_path) -> None:
    db_path, settings, raw = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get("/v1/conversations/search?q=release&scope=messages&backend=fts", headers=headers)
    if not is_fts5_available(db_path):
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "fts_unavailable"
        return

    assert response.status_code == 200
    payload = response.json()
    assert payload["search"]["backend"] == "fts"
    assert all(item["search_backend"] == "fts" for item in payload["messages"])


def test_invalid_backend_returns_error(client, monkeypatch, tmp_path) -> None:
    _db_path, settings, raw = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get("/v1/conversations/search?q=release&scope=messages&backend=weird", headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_search_backend"


def test_auto_falls_back_to_like_when_fts_fails(client, monkeypatch, tmp_path) -> None:
    _db_path, settings, raw = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.conversations.is_fts5_available", lambda _db: True)
    monkeypatch.setattr(
        "app.storage.conversations._search_messages_fts",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced_fts_failure")),
    )
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get("/v1/conversations/search?q=release&scope=messages&backend=auto", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["search"]["backend"] == "like"
    assert payload["search"]["fallback_used"] is True
    assert all(item["search_backend"] == "like" for item in payload["messages"])
