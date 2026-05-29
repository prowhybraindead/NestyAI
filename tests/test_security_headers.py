from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.security_headers import SecurityHeadersMiddleware


def _build_test_app(enable_hsts: bool) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=enable_hsts)

    @app.get("/v1/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_security_headers_present_when_enabled() -> None:
    client = TestClient(_build_test_app(enable_hsts=False))
    response = client.get("/v1/ping")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "no-referrer"
    assert response.headers.get("permissions-policy") == "camera=(), microphone=(), geolocation=()"
    assert response.headers.get("cache-control") == "no-store"
    assert "strict-transport-security" not in response.headers


def test_hsts_header_only_when_enabled() -> None:
    client = TestClient(_build_test_app(enable_hsts=True))
    response = client.get("/v1/ping")
    assert response.status_code == 200
    assert response.headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"
