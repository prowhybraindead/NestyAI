from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.datastructures import MutableHeaders


class SecurityHeadersMiddleware:
    def __init__(self, app, enable_hsts: bool = False) -> None:
        self.app = app
        self.enable_hsts = bool(enable_hsts)

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        send: Callable[[dict], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

                # Keep API responses non-cacheable by default.
                if path.startswith("/v1/") or path in {"/health", "/ready"}:
                    headers.setdefault("Cache-Control", "no-store")

                if self.enable_hsts:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)
