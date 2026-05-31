from __future__ import annotations

import httpx


_shared_async_client: httpx.AsyncClient | None = None


def get_shared_async_client(timeout_seconds: float = 30.0) -> httpx.AsyncClient:
    global _shared_async_client
    if _shared_async_client is None:
        _shared_async_client = httpx.AsyncClient(timeout=timeout_seconds)
    return _shared_async_client


async def close_shared_async_client() -> None:
    global _shared_async_client
    if _shared_async_client is not None:
        await _shared_async_client.aclose()
        _shared_async_client = None
