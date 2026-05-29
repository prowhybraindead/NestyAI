from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_cors_disabled_by_default_has_no_cors_headers(tmp_path) -> None:
    settings = Settings(
        nesty_db_path=str(tmp_path / "cors_disabled.db"),
        cors_enabled=False,
        security_headers_enabled=False,
    )
    client = TestClient(create_app(settings=settings))
    response = client.get("/health", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_enabled_specific_origin_allows_origin(tmp_path) -> None:
    settings = Settings(
        nesty_db_path=str(tmp_path / "cors_enabled.db"),
        cors_enabled=True,
        cors_allow_origins="https://app.example.com",
        cors_allow_methods="GET,POST,OPTIONS",
        cors_allow_headers="Authorization,Content-Type",
        security_headers_enabled=False,
    )
    client = TestClient(create_app(settings=settings))
    response = client.options(
        "/v1/chat/completions",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://app.example.com"


def test_wildcard_cors_rejected_in_production_with_required_api_key(tmp_path) -> None:
    settings = Settings(
        nesty_db_path=str(tmp_path / "cors_unsafe.db"),
        app_env="production",
        require_api_key=True,
        cors_enabled=True,
        cors_allow_origins="*",
        security_headers_enabled=False,
    )
    with pytest.raises(RuntimeError) as exc_info:
        create_app(settings=settings)
    assert "unsafe_cors_configuration" in str(exc_info.value)


def test_trusted_hosts_can_be_configured(tmp_path) -> None:
    settings = Settings(
        nesty_db_path=str(tmp_path / "trusted_hosts.db"),
        trusted_hosts="testserver,localhost,127.0.0.1",
        cors_enabled=False,
        security_headers_enabled=False,
    )
    client = TestClient(create_app(settings=settings))
    response = client.get("/health")
    assert response.status_code == 200
