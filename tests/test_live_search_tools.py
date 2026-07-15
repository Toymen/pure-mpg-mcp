"""Opt-in live checks for search/retrieval/export/file critical MCP tools.

Run with:
    uv run --extra dev pytest -m network

These tests intentionally touch the public PuRe service. They use low-volume
requests and stable public IDs, but they are still network tests: upstream
outages should not block the normal offline suite.
"""

from __future__ import annotations

import pytest

from pure_mpg_mcp import server

from fixtures_live import LIVE_DOI, LIVE_FILE_ID, LIVE_FILE_ITEM_ID, LIVE_ITEM_ID, identifier_query

pytestmark = [pytest.mark.network, pytest.mark.asyncio(loop_scope="session")]


async def test_live_publication_search_retrieval_export_and_files():
    search = await server.search_publications(identifier=LIVE_DOI, size=1)
    assert search["numberOfRecords"] >= 1
    assert search["items"][0]["itemId"] == LIVE_ITEM_ID

    raw = await server.search_raw(identifier_query(), size=1)
    assert raw["items"][0]["itemId"] == LIVE_ITEM_ID

    by_doi = await server.find_by_doi(f"https://doi.org/{LIVE_DOI}")
    assert by_doi["items"][0]["itemId"] == LIVE_ITEM_ID

    item = await server.get_publication(LIVE_ITEM_ID)
    assert item["objectId"] == LIVE_ITEM_ID
    assert item["metadata"]["title"]

    item_export = await server.export_publication(LIVE_ITEM_ID)
    assert LIVE_DOI in item_export

    search_export = await server.export_search_results(query=identifier_query(), size=1)
    assert LIVE_DOI in search_export

    file_meta = await server.get_file_metadata(LIVE_FILE_ITEM_ID, LIVE_FILE_ID)
    assert file_meta["contentUrl"].endswith(f"/items/{LIVE_FILE_ITEM_ID}/component/{LIVE_FILE_ID}/content")
    assert file_meta["thumbnailUrl"].endswith(f"/items/{LIVE_FILE_ITEM_ID}/component/{LIVE_FILE_ID}/thumbnail")
    assert any(key.startswith(("pdf:", "X-TIKA:")) for key in file_meta)
