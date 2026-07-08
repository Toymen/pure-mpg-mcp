"""Offline tests for PureClient's bulk offset-pagination helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp.client import PureClient


async def test_fetch_all_no_cap():
    """fetch_all(max_records=None) pages via offset until all records returned."""
    client = PureClient()
    rec1 = {"data": {"objectId": "item_1"}}
    rec2 = {"data": {"objectId": "item_2"}}
    rec3 = {"data": {"objectId": "item_3"}}
    page1 = {"numberOfRecords": 3, "records": [rec1, rec2]}
    page2 = {"numberOfRecords": 3, "records": [rec3]}
    page3 = {"numberOfRecords": 3, "records": []}

    mock = AsyncMock(side_effect=[page1, page2, page3])
    with (
        patch.object(client, "search_items", new=mock),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await client.fetch_all({"match_all": {}}, max_records=None)

    assert result == [rec1, rec2, rec3]
    # second call must use from_=2 (offset after the 2 records from page 1)
    _, kwargs = mock.call_args_list[1]
    assert kwargs.get("from_") == 2
    await client.aclose()


async def test_fetch_all_with_cap():
    """fetch_all(max_records=N) stops once N records are collected."""
    client = PureClient()
    rec1 = {"data": {"objectId": "item_1"}}
    rec2 = {"data": {"objectId": "item_2"}}
    page1 = {"numberOfRecords": 10, "records": [rec1, rec2]}

    with patch.object(client, "search_items", new=AsyncMock(return_value=page1)):
        result = await client.fetch_all({"match_all": {}}, max_records=2)

    assert result == [rec1, rec2]
    await client.aclose()


async def test_fetch_all_pages_past_ten_thousand_records():
    """Offset pagination has no artificial ceiling (verified live past 500k historically)."""
    client = PureClient()
    total = 12_000
    calls = 0

    async def search_items(query, size, from_):
        nonlocal calls
        calls += 1
        remaining = total - from_
        batch = min(size, remaining)
        return {
            "numberOfRecords": total,
            "records": [{"data": {"objectId": f"item_{from_ + i}"}} for i in range(batch)],
        }

    with (
        patch.object(client, "search_items", new=search_items),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await client.fetch_all({"match_all": {}}, max_records=None, page_size=1000)

    assert len(result) == total
    assert calls == 12
    await client.aclose()


async def test_fetch_all_caps_page_size_to_live_safe_limit():
    client = PureClient()
    page = {"numberOfRecords": 1, "records": [{"data": {"objectId": "item_1"}}]}
    mock = AsyncMock(return_value=page)

    with patch.object(client, "search_items", new=mock):
        result = await client.fetch_all({"match_all": {}}, max_records=None, page_size=50_000)

    assert result == page["records"]
    assert mock.call_args.kwargs["size"] == 20_000
    await client.aclose()


async def test_fetch_pages_yields_without_accumulating_everything():
    client = PureClient()
    recs = [{"data": {"objectId": f"item_{i}"}} for i in range(5)]

    async def search_items(query, size, from_):
        return {"numberOfRecords": len(recs), "records": recs[from_:from_ + size]}

    with (
        patch.object(client, "search_items", new=search_items),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        pages = [page async for page in client.fetch_pages({"match_all": {}}, page_size=2)]

    assert [[r["data"]["objectId"] for r in page] for page in pages] == [
        ["item_0", "item_1"],
        ["item_2", "item_3"],
        ["item_4"],
    ]
    await client.aclose()
