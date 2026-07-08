"""Offline tests for PureClient's shared retry/backoff transport logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from pure_mpg_mcp.client import PureClient

from fixtures_pure import mock_transport


async def test_search_items_retries_retryable_http_errors():
    client = PureClient(base_url="https://pure.test/rest")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="slow down", request=request)
        return httpx.Response(200, json={"numberOfRecords": 0, "records": []}, request=request)

    mock_transport(client, handler)
    with patch.object(client, "_sleep_before_retry", new=AsyncMock()) as sleep:
        out = await client.search_items({"match_all": {}}, size=0)

    assert out["numberOfRecords"] == 0
    assert calls == 2
    sleep.assert_awaited_once()
    await client.aclose()


async def test_search_items_does_not_retry_bad_requests():
    client = PureClient(base_url="https://pure.test/rest")

    def handler(request):
        return httpx.Response(400, text="bad request", request=request)

    mock_transport(client, handler)
    with (
        pytest.raises(httpx.HTTPStatusError),
        patch.object(client, "_sleep_before_retry", new=AsyncMock()) as sleep,
    ):
        await client.search_items({"match_all": {}}, size=0)

    sleep.assert_not_awaited()
    await client.aclose()


async def test_get_retries_5xx_then_raises_after_exhausting_attempts():
    """GET requests (get_item, feeds, OU lookups, ...) retry 5xx/429 too.

    Retries live in the shared `_send_with_retries` used by both `_get` and
    `_post_json`, not bolted onto one endpoint — a fresh call always inherits
    it.
    """
    c = PureClient(base_url="https://pure.test/rest")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    mock_transport(c, handler)
    with patch.object(c, "_sleep_before_retry", new=AsyncMock()) as sleep:
        async with c:
            with pytest.raises(httpx.HTTPStatusError):
                await c.get_item("item_1")

    assert calls == 4  # 1 initial attempt + 3 retries (DEFAULT_RETRIES)
    assert sleep.await_count == 3


def test_base_url_env_fallback(monkeypatch):
    monkeypatch.setenv("PURE_BASE_URL", "https://env.test/rest/")
    assert PureClient().base_url == "https://env.test/rest"
