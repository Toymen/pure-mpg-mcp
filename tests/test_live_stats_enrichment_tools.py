"""Opt-in live checks for authority/statistics/analysis/enrichment critical MCP tools.

Run with:
    uv run --extra dev pytest -m network
"""

from __future__ import annotations

import httpx
import pytest

from pure_mpg_mcp import server
from pure_mpg_mcp.client import PureClient
from pure_mpg_mcp.enrichment import unavailable_sources

from fixtures_live import LIVE_DOI, LIVE_ITEM_ID, assert_feed, identifier_query

pytestmark = [pytest.mark.network, pytest.mark.asyncio(loop_scope="module")]


async def test_live_authority_statistics_analysis_and_enrichment_tools():
    languages = await server.list_languages()
    codes = {entry["id"] for entry in languages["languages"]}
    assert {"eng", "deu"}.issubset(codes)

    authors = await server.resolve_author(name="Planck", limit=2)
    assert authors["candidates"]
    person = await server.resolve_author(person_id=authors["candidates"][0]["id"])
    assert person["personId"]

    author_publications = await server.author_publications(name="Planck", size=1)
    assert author_publications["numberOfRecords"] >= 1

    author_analysis = await server.analyze_authors(item_id=LIVE_ITEM_ID)
    assert author_analysis["summary"]["analyzedRecords"] == 1
    assert author_analysis["authors"]

    stats = await server.publication_statistics(query=identifier_query(), group_by="open_access")
    assert {bucket["key"] for bucket in stats["buckets"]} == {"open_access", "closed"}
    assert stats["totalMatchingRecords"] >= 1

    metrics = await server.get_citation_metrics(doi=LIVE_DOI)
    if "error" in metrics:
        pytest.skip(f"enrichment sources unavailable for {LIVE_DOI}: {metrics['error']}")
    assert any(
        metrics.get(key) is not None
        for key in ("openalex_cited_by", "crossref_referenced_by", "semanticscholar_citations")
    )

    full_text = await server.find_full_text(item_id=LIVE_ITEM_ID)
    assert full_text["doi"] == LIVE_DOI
    if "unpaywall" in unavailable_sources(["unpaywall"]):
        assert full_text["notes"]["unpaywall"] == unavailable_sources(["unpaywall"])["unpaywall"]


@pytest.mark.limit
async def test_live_known_feed_search_limitation_is_explicit():
    """The live feed/search endpoint currently returns HTTP 500 for normal q values."""
    async with PureClient() as client:
        try:
            text = await client.feed_search("graphene")
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code >= 500
            assert "JsonParsingException" in exc.response.text
        else:
            assert_feed(text)
