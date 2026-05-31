from __future__ import annotations

import pytest

from app.core.http_client import close_shared_async_client, get_shared_async_client


@pytest.mark.asyncio
async def test_shared_async_client_reused_and_recreated_after_close() -> None:
    first = get_shared_async_client(timeout_seconds=5.0)
    second = get_shared_async_client(timeout_seconds=30.0)
    assert first is second

    await close_shared_async_client()

    third = get_shared_async_client(timeout_seconds=5.0)
    assert third is not first

    await close_shared_async_client()
