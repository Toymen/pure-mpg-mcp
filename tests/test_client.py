"""Live smoke tests against the public PuRe API.

These hit the network. Run only the offline tests with:
    pytest -m "not network"
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from pure_mpg_mcp.client import PureClient
from pure_mpg_mcp.models import summarize_item, summarize_search


def test_summarize_item_minimal():
    rec = {
        "data": {
            "objectId": "item_1",
            "objectPid": "hdl:123",
            "publicState": "RELEASED",
            "metadata": {
                "title": "A Title",
                "genre": "ARTICLE",
                "creators": [
                    {"person": {"familyName": "Planck", "givenName": "Max"}}
                ],
                "identifiers": [{"type": "DOI", "id": "10.1/x"}],
            },
        }
    }
    out = summarize_item(rec)
    assert out["itemId"] == "item_1"
    assert out["title"] == "A Title"
    assert out["creators"] == ["Planck, Max"]
    assert out["doi"] == "10.1/x"


def test_summarize_item_includes_organization_creators():
    """PubMan creators can be PERSON or ORGANIZATION (corporate authors) — both must show up."""
    rec = {
        "data": {
            "objectId": "item_2",
            "metadata": {
                "title": "A Report",
                "creators": [
                    {"type": "PERSON", "person": {"familyName": "Planck", "givenName": "Max"}},
                    {"type": "ORGANIZATION", "organization": {"name": "Max Planck Society"}},
                ],
            },
        }
    }
    out = summarize_item(rec)
    assert out["creators"] == ["Planck, Max", "Max Planck Society"]


def test_summarize_search_shape():
    payload = {"numberOfRecords": 1, "records": [{"data": {"objectId": "item_9"}}]}
    out = summarize_search(payload)
    assert out["numberOfRecords"] == 1
    assert out["items"][0]["itemId"] == "item_9"


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


async def test_search_items_retries_retryable_http_errors():
    client = PureClient(base_url="https://pure.test/rest")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="slow down", request=request)
        return httpx.Response(200, json={"numberOfRecords": 0, "records": []}, request=request)

    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://pure.test/rest",
        headers={"Accept": "application/json"},
    )
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

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://pure.test/rest")
    with (
        pytest.raises(httpx.HTTPStatusError),
        patch.object(client, "_sleep_before_retry", new=AsyncMock()) as sleep,
    ):
        await client.search_items({"match_all": {}}, size=0)

    sleep.assert_not_awaited()
    await client.aclose()


def test_is_open_access_uses_comp_visibility():
    """OA check reads visibility from the component root, not component.metadata."""
    from pure_mpg_mcp.analysis import is_open_access

    rec_oa = {"data": {"files": [{"visibility": "PUBLIC", "metadata": {}}]}}
    rec_closed = {"data": {"files": [{"visibility": "PRIVATE", "metadata": {}}]}}
    rec_no_files = {"data": {"files": []}}

    assert is_open_access(rec_oa) is True
    assert is_open_access(rec_closed) is False
    assert is_open_access(rec_no_files) is False


@pytest.mark.network
async def test_service_info_live():
    async with PureClient() as c:
        info = await c.service_info()
        assert isinstance(info, dict)


@pytest.mark.network
async def test_search_live():
    async with PureClient() as c:
        payload = await c.search_items(query={"match_all": {}}, size=2)
        assert payload["numberOfRecords"] > 0
        assert len(payload["records"]) == 2
