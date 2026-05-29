from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_ready_endpoint_returns_database_ok(tmp_path) -> None:
    settings = Settings(
        nesty_db_path=str(tmp_path / "ready.db"),
        security_headers_enabled=False,
        cors_enabled=False,
    )
    client = TestClient(create_app(settings=settings))
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["service"] == "nesty-ai"
    assert payload["database"] == "ok"
