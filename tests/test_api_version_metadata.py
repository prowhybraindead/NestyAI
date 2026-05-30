"""tests/test_api_version_metadata.py

Tests that:
- Every HTTP response carries the X-Nesty-API-Version header.
- The / root, /health, and /ready responses include version and api_version fields.
- VERSION constant is importable and non-empty.
- No real providers are called.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.version import VERSION, API_VERSION


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        nesty_db_path=str(tmp_path / "test.db"),
        require_api_key=False,
        public_health=True,
        security_headers_enabled=False,
    )
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# VERSION constant sanity
# ---------------------------------------------------------------------------

def test_version_constant_is_non_empty() -> None:
    assert VERSION, "app.version.VERSION must not be empty"
    assert isinstance(VERSION, str)


def test_api_version_constant_is_v1() -> None:
    assert API_VERSION == "v1"


# ---------------------------------------------------------------------------
# X-Nesty-API-Version response header
# ---------------------------------------------------------------------------

def test_root_has_version_header(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers.get("x-nesty-api-version") == VERSION


def test_health_has_version_header(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-nesty-api-version") == VERSION


def test_ready_has_version_header(client) -> None:
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.headers.get("x-nesty-api-version") == VERSION


def test_models_endpoint_has_version_header(client) -> None:
    r = client.get("/v1/models")
    assert r.status_code == 200
    assert r.headers.get("x-nesty-api-version") == VERSION


# ---------------------------------------------------------------------------
# Root / response shape
# ---------------------------------------------------------------------------

def test_root_response_contains_version_field(client) -> None:
    body = client.get("/").json()
    assert "version" in body
    assert body["version"] == VERSION


def test_root_response_contains_api_version_field(client) -> None:
    body = client.get("/").json()
    assert "api_version" in body
    assert body["api_version"] == "v1"


def test_root_response_contains_name_and_description(client) -> None:
    body = client.get("/").json()
    assert "name" in body
    assert "description" in body


# ---------------------------------------------------------------------------
# /health response shape
# ---------------------------------------------------------------------------

def test_health_response_shape(client) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "nesty-ai"
    assert body["version"] == VERSION
    assert body["api_version"] == "v1"


# ---------------------------------------------------------------------------
# /ready response shape
# ---------------------------------------------------------------------------

def test_ready_response_shape(client) -> None:
    body = client.get("/ready").json()
    assert body["status"] == "ready"
    assert body["service"] == "nesty-ai"
    assert body["database"] == "ok"
    assert body["version"] == VERSION
    assert body["api_version"] == "v1"
