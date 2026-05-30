from __future__ import annotations

from app.schemas.embeddings import EmbeddingResult


def test_internal_embedding_endpoint_hidden_when_internal_admin_disabled(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.security.internal_auth.get_settings",
        lambda: type("S", (), {"internal_admin_enabled": False, "nesty_internal_admin_token": "abc"})(),
    )
    response = client.post("/internal/embeddings/test", json={"text": "hello"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "internal_admin_disabled"


def test_internal_embedding_endpoint_requires_token(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.security.internal_auth.get_settings",
        lambda: type("S", (), {"internal_admin_enabled": True, "nesty_internal_admin_token": "abc"})(),
    )
    monkeypatch.setattr(
        "app.api.internal_embeddings.get_settings",
        lambda: type("S", (), {"embeddings_enabled": True})(),
    )
    response = client.post("/internal/embeddings/test", json={"text": "hello"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "internal_admin_unauthorized"


def test_internal_embedding_endpoint_returns_dimensions_without_vector(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.security.internal_auth.get_settings",
        lambda: type("S", (), {"internal_admin_enabled": True, "nesty_internal_admin_token": "abc"})(),
    )
    monkeypatch.setattr(
        "app.api.internal_embeddings.get_settings",
        lambda: type("S", (), {"embeddings_enabled": True})(),
    )

    async def _mock_generate_embedding(text: str, provider: str | None = None, model: str | None = None):
        return EmbeddingResult(
            provider=provider or "openrouter",
            model=model or "nvidia/llama-nemotron-embed-vl-1b-v2:free",
            embedding=[0.1, 0.2, 0.3],
            dimensions=3,
            usage={"total_tokens": 1},
            latency_ms=10,
        )

    monkeypatch.setattr("app.api.internal_embeddings.generate_embedding", _mock_generate_embedding)

    response = client.post(
        "/internal/embeddings/test",
        headers={"Authorization": "Bearer abc"},
        json={"text": "hello world", "provider": "openrouter"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["dimensions"] == 3
    assert "embedding" not in payload
