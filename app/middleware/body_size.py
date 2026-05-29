from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from app.core.errors import build_error_response


class BodySizeLimitMiddleware:
    def __init__(self, app, max_request_body_bytes: int = 1048576) -> None:
        self.app = app
        self.max_request_body_bytes = max(1, int(max_request_body_bytes))

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        send: Callable[[dict], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw_content_length = headers.get(b"content-length")
        if raw_content_length is not None:
            try:
                content_length = int(raw_content_length.decode("latin1"))
            except (TypeError, ValueError):
                content_length = -1
            if content_length > self.max_request_body_bytes:
                payload = build_error_response(
                    code="request_too_large",
                    message="Request body is too large.",
                )
                body = json.dumps(payload).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("latin1")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body, "more_body": False})
                return

        await self.app(scope, receive, send)
