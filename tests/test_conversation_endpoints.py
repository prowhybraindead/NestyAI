from __future__ import annotations

from app.config import Settings
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import add_message, create_conversation
from app.storage.db import init_db


def test_conversation_endpoints_crud(client, monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "conversation_endpoints.db")
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
    key = create_api_key_record(db_path=db_path, name="owner", raw_key=raw_key, hash_secret="secret123")
    conv = create_conversation(api_key_id=key["id"], title="initial", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="hello", db_path=db_path)

    headers = {"Authorization": f"Bearer {raw_key}"}

    list_resp = client.get("/v1/conversations?limit=20&offset=0", headers=headers)
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()["data"]]
    assert conv["id"] in ids

    detail_resp = client.get(f"/v1/conversations/{conv['id']}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["conversation"]["id"] == conv["id"]
    assert len(detail_resp.json()["messages"]) >= 1

    patch_resp = client.patch(
        f"/v1/conversations/{conv['id']}",
        headers=headers,
        json={"title": "renamed"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["ok"] is True

    delete_resp = client.delete(f"/v1/conversations/{conv['id']}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["ok"] is True

    list_after = client.get("/v1/conversations?limit=20&offset=0", headers=headers)
    assert list_after.status_code == 200
    ids_after = [item["id"] for item in list_after.json()["data"]]
    assert conv["id"] not in ids_after
