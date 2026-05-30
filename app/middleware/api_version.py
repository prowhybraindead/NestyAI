from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.datastructures import MutableHeaders

from app.version import VERSION


class APIVersionHeaderMiddleware:
    """Injects ``X-Nesty-API-Version`` into every HTTP response.

    This is a passive, read-only middleware – it never alters request routing
    or response bodies.  Adding the header makes it trivial for clients to
    confirm which server version they are talking to.
    """

    def __init__(self, app) -> None:
        self.app = app
        self._version_value = VERSION

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        send: Callable[[dict], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Nesty-API-Version", self._version_value)
            await send(message)

        await self.app(scope, receive, send_wrapper)
