"""Live smoke tests against the public PuRe API.

These hit the network. Run only the offline tests with:
    pytest -m "not network"
"""

from unittest.mock import AsyncMock, patch

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


def test_summarize_search_shape():
    payload = {"numberOfRecords": 1, "records": [{"data": {"objectId": "item_9"}}]}
    out = summarize_search(payload)
    assert out["numberOfRecords"] == 1
    assert out["items"][0]["itemId"] == "item_9"


async def test_fetch_all_no_cap():
    """fetch_all(max_records=None) scrolls until all records are returned."""
    client = PureClient()
    page1 = {"numberOfRecords": 3, "records": ["r1", "r2"], "scrollId": "sid1"}
    page2 = {"numberOfRecords": 3, "records": ["r3"], "scrollId": None}

    with (
        patch.object(client, "search_items", new=AsyncMock(return_value=page1)),
        patch.object(client, "scroll_items", new=AsyncMock(return_value=page2)),
    ):
        result = await client.fetch_all({"match_all": {}}, max_records=None)

    assert result == ["r1", "r2", "r3"]
    await client.aclose()


async def test_fetch_all_with_cap():
    """fetch_all(max_records=N) stops once N records are collected."""
    client = PureClient()
    page1 = {"numberOfRecords": 10, "records": ["r1", "r2"], "scrollId": "sid1"}

    with patch.object(client, "search_items", new=AsyncMock(return_value=page1)):
        result = await client.fetch_all({"match_all": {}}, max_records=2)

    assert result == ["r1", "r2"]
    await client.aclose()


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
