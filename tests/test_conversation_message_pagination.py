from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import add_message, create_conversation
from app.storage.db import init_db


def _setup(tmp_path):
    db_path = str(tmp_path / "conversation_pagination.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
    )
    raw = generate_api_key("dev")
    key = create_api_key_record(db_path, "owner", raw, hash_secret="secret123")
    conv = create_conversation(api_key_id=key["id"], title="pager", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="m1", db_path=db_path)
    add_message(conversation_id=conv["id"], role="assistant", content="m2", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="m3", db_path=db_path)
    return db_path, settings, raw, conv["id"]


def test_messages_pagination_asc_desc_and_has_more(client, monkeypatch, tmp_path) -> None:
    db_path, settings, raw, conv_id = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw}"}

    asc_resp = client.get(
        f"/v1/conversations/{conv_id}/messages?limit=2&offset=0&order=asc",
        headers=headers,
    )
    assert asc_resp.status_code == 200
    asc_payload = asc_resp.json()
    assert asc_payload["pagination"]["has_more"] is True
    assert [item["content"] for item in asc_payload["data"]] == ["m1", "m2"]

    desc_resp = client.get(
        f"/v1/conversations/{conv_id}/messages?limit=2&offset=0&order=desc",
        headers=headers,
    )
    assert desc_resp.status_code == 200
    desc_payload = desc_resp.json()
    assert [item["content"] for item in desc_payload["data"]] == ["m3", "m2"]

    tail_resp = client.get(
        f"/v1/conversations/{conv_id}/messages?limit=2&offset=2&order=asc",
        headers=headers,
    )
    assert tail_resp.status_code == 200
    tail_payload = tail_resp.json()
    assert tail_payload["pagination"]["has_more"] is False
    assert [item["content"] for item in tail_payload["data"]] == ["m3"]


def test_messages_pagination_limit_max_and_invalid_order(client, monkeypatch, tmp_path) -> None:
    db_path, settings, raw, conv_id = _setup(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {raw}"}

    too_large = client.get(
        f"/v1/conversations/{conv_id}/messages?limit=101&offset=0&order=asc",
        headers=headers,
    )
    assert too_large.status_code == 400
    assert too_large.json()["error"]["code"] == "invalid_conversation_request"

    invalid_order = client.get(
        f"/v1/conversations/{conv_id}/messages?limit=20&offset=0&order=weird",
        headers=headers,
    )
    assert invalid_order.status_code == 400
    assert invalid_order.json()["error"]["code"] == "invalid_conversation_request"
