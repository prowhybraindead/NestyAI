from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import archive_conversation, create_conversation
from app.storage.db import init_db


def test_archived_filters_active_archived_all(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "conversation_filters.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)

    raw = generate_api_key("dev")
    key = create_api_key_record(db_path, "owner", raw, hash_secret="secret123")
    active = create_conversation(api_key_id=key["id"], title="Active One", db_path=db_path)
    archived = create_conversation(api_key_id=key["id"], title="Archived One", db_path=db_path)
    archive_conversation(archived["id"], api_key_id=key["id"], db_path=db_path)

    headers = {"Authorization": f"Bearer {raw}"}

    resp_active = client.get("/v1/conversations?archived=active", headers=headers)
    assert resp_active.status_code == 200
    active_ids = [item["id"] for item in resp_active.json()["data"]]
    assert active["id"] in active_ids
    assert archived["id"] not in active_ids

    resp_archived = client.get("/v1/conversations?archived=archived", headers=headers)
    assert resp_archived.status_code == 200
    archived_ids = [item["id"] for item in resp_archived.json()["data"]]
    assert archived["id"] in archived_ids
    assert active["id"] not in archived_ids

    resp_all = client.get("/v1/conversations?archived=all", headers=headers)
    assert resp_all.status_code == 200
    all_ids = [item["id"] for item in resp_all.json()["data"]]
    assert active["id"] in all_ids
    assert archived["id"] in all_ids


def test_list_filter_q_searches_title(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "conversation_filters_q.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)

    raw = generate_api_key("dev")
    key = create_api_key_record(db_path, "owner", raw, hash_secret="secret123")
    conv_1 = create_conversation(api_key_id=key["id"], title="Travel Plan", db_path=db_path)
    _conv_2 = create_conversation(api_key_id=key["id"], title="Shopping List", db_path=db_path)

    headers = {"Authorization": f"Bearer {raw}"}
    resp = client.get("/v1/conversations?archived=all&q=Travel", headers=headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["data"]]
    assert conv_1["id"] in ids
    assert len(ids) == 1
