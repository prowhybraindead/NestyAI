from __future__ import annotations

from types import SimpleNamespace

from app.config import Settings
from app.schemas.provider import ProviderChatResult
from app.security.api_key import generate_api_key
from app.storage.api_keys import create_api_key_record
from app.storage.conversations import (
    add_message,
    create_conversation,
    get_conversation,
    get_recent_messages,
    update_conversation_summary,
)
from app.storage.db import init_db


class _SummaryRouter:
    async def route_chat(self, request_id: str, model_alias: str, messages, temperature: float, max_tokens: int):
        return SimpleNamespace(provider_result=ProviderChatResult(provider="openrouter", content="summary updated"))


class _SummaryOrchestrator:
    def __init__(self) -> None:
        self.router = _SummaryRouter()


def _setup_auth_db(tmp_path):
    db_path = str(tmp_path / "conversation_controls.db")
    init_db(db_path)
    settings = Settings(
        nesty_db_path=db_path,
        nesty_api_key_hash_secret="secret123",
        require_api_key=True,
        rate_limit_enabled=False,
        conversation_summary_enabled=True,
        conversation_summary_trigger_messages=30,
    )
    raw_a = generate_api_key("dev")
    raw_b = generate_api_key("dev")
    key_a = create_api_key_record(db_path, "key-a", raw_a, hash_secret="secret123")
    key_b = create_api_key_record(db_path, "key-b", raw_b, hash_secret="secret123")
    return db_path, settings, raw_a, raw_b, key_a, key_b


def test_reset_clear_and_summarize_controls(client, monkeypatch, tmp_path) -> None:
    db_path, settings, raw_a, _, key_a, _ = _setup_auth_db(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.conversations.get_orchestrator", lambda: _SummaryOrchestrator())
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)

    conv = create_conversation(api_key_id=key_a["id"], title="ctrl", db_path=db_path)
    conv_id = conv["id"]
    add_message(conversation_id=conv_id, role="user", content="m1", db_path=db_path)
    add_message(conversation_id=conv_id, role="assistant", content="m2", db_path=db_path)
    update_conversation_summary(conv_id, "old-summary", 1, db_path=db_path)

    headers = {"Authorization": f"Bearer {raw_a}"}

    reset_resp = client.post(f"/v1/conversations/{conv_id}/reset-summary", headers=headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["ok"] is True
    after_reset = get_conversation(conv_id, db_path=db_path)
    assert after_reset is not None
    assert after_reset["summary"] is None
    assert after_reset["summary_message_count"] == 0
    assert len(get_recent_messages(conv_id, limit=20, db_path=db_path)) == 2

    summarize_resp = client.post(f"/v1/conversations/{conv_id}/summarize", headers=headers)
    assert summarize_resp.status_code == 200
    assert summarize_resp.json()["ok"] is True
    assert summarize_resp.json()["summary_updated"] is True

    clear_keep_resp = client.post(
        f"/v1/conversations/{conv_id}/clear",
        headers=headers,
        json={"keep_summary": True},
    )
    assert clear_keep_resp.status_code == 200
    after_clear_keep = get_conversation(conv_id, db_path=db_path)
    assert after_clear_keep is not None
    assert len(get_recent_messages(conv_id, limit=20, db_path=db_path)) == 0
    assert bool(str(after_clear_keep["summary"] or "").strip()) is True

    add_message(conversation_id=conv_id, role="user", content="new", db_path=db_path)
    clear_all_resp = client.post(
        f"/v1/conversations/{conv_id}/clear",
        headers=headers,
        json={"keep_summary": False},
    )
    assert clear_all_resp.status_code == 200
    after_clear_all = get_conversation(conv_id, db_path=db_path)
    assert after_clear_all is not None
    assert len(get_recent_messages(conv_id, limit=20, db_path=db_path)) == 0
    assert after_clear_all["summary"] is None
    assert after_clear_all["summary_message_count"] == 0


def test_summarize_endpoint_no_messages_returns_not_updated(client, monkeypatch, tmp_path) -> None:
    db_path, settings, raw_a, _, key_a, _ = _setup_auth_db(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.conversations.get_orchestrator", lambda: _SummaryOrchestrator())
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)

    conv = create_conversation(api_key_id=key_a["id"], title="empty", db_path=db_path)
    headers = {"Authorization": f"Bearer {raw_a}"}
    resp = client.post(f"/v1/conversations/{conv['id']}/summarize", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["summary_updated"] is False


def test_cross_key_access_denied_for_controls(client, monkeypatch, tmp_path) -> None:
    db_path, settings, _, raw_b, key_a, _ = _setup_auth_db(tmp_path)
    monkeypatch.setattr("app.api.conversations.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.conversations.get_orchestrator", lambda: _SummaryOrchestrator())
    monkeypatch.setattr("app.security.auth.get_settings", lambda: settings)

    conv = create_conversation(api_key_id=key_a["id"], title="owned", db_path=db_path)
    add_message(conversation_id=conv["id"], role="user", content="hello", db_path=db_path)
    headers_b = {"Authorization": f"Bearer {raw_b}"}

    for method, path, body in [
        ("post", f"/v1/conversations/{conv['id']}/clear", {"keep_summary": False}),
        ("post", f"/v1/conversations/{conv['id']}/reset-summary", None),
        ("post", f"/v1/conversations/{conv['id']}/summarize", None),
        ("get", f"/v1/conversations/{conv['id']}/export", None),
    ]:
        if method == "post":
            resp = client.post(path, headers=headers_b, json=body)
        else:
            resp = client.get(path, headers=headers_b)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "conversation_not_found"
