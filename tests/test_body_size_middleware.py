from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.errors import APIError, build_error_response
from app.middleware.body_size import BodySizeLimitMiddleware


def _build_test_app(limit_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_request_body_bytes=limit_bytes)

    @app.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        payload = build_error_response(exc.code, exc.message, exc.details)
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)

    @app.post("/echo")
    async def echo(payload: dict) -> dict:
        return {"ok": True, "payload": payload}

    return app


def test_request_too_large_returns_413() -> None:
    client = TestClient(_build_test_app(limit_bytes=32))
    response = client.post("/echo", json={"text": "x" * 100})
    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "request_too_large"
    assert body["error"]["message"] == "Request body is too large."
