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
    """fetch_all(max_records=None) pages via search_after until all records returned."""
    client = PureClient()
    rec1 = {"data": {"objectId": "item_1"}}
    rec2 = {"data": {"objectId": "item_2"}}
    rec3 = {"data": {"objectId": "item_3"}}
    page1 = {"numberOfRecords": 3, "records": [rec1, rec2]}
    page2 = {"numberOfRecords": 3, "records": [rec3]}
    page3 = {"numberOfRecords": 3, "records": []}

    mock = AsyncMock(side_effect=[page1, page2, page3])
    with patch.object(client, "search_items", new=mock):
        result = await client.fetch_all({"match_all": {}}, max_records=None)

    assert result == [rec1, rec2, rec3]
    # second call must carry search_after with the last id of page 1
    _, kwargs = mock.call_args_list[1]
    assert kwargs.get("search_after") == ["item_2"]
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
