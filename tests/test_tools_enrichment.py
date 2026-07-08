"""Offline tests for enrich_publication and get_citation_metrics tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server

from helpers import _item_with_doi


async def test_enrich_publication_rejects_unknown_source():
    out = await server.enrich_publication(doi="10.1/x", sources=["openalex", "nope"])
    assert "unknown source(s)" in out["error"]


async def test_enrich_publication_requires_doi():
    with patch.object(server._client, "get_item", new=AsyncMock(return_value=_item_with_doi(None))):
        out = await server.enrich_publication(item_id="item_d")
    assert out["error"] == "no DOI available for this publication"


async def test_enrich_publication_success_from_item():
    enrichment = {"openalex": {"cited_by_count": 12}}
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value=_item_with_doi("10.1/x"))),
        patch.object(server._enrich, "fetch", new=AsyncMock(return_value=enrichment)) as fetch,
    ):
        out = await server.enrich_publication(item_id="item_d", sources=["openalex"])
    assert out["doi"] == "10.1/x"
    assert out["sourcesReturned"] == ["openalex"]
    assert out["pure"]["itemId"] == "item_d"
    fetch.assert_awaited_once_with("10.1/x", ["openalex"])


async def test_get_citation_metrics():
    data = {
        "openalex": {"cited_by_count": 10},
        "crossref": {"is_referenced_by_count": 8},
        "semanticscholar": {"citation_count": 9, "influential_citation_count": 2},
    }
    with patch.object(server._enrich, "fetch", new=AsyncMock(return_value=data)):
        out = await server.get_citation_metrics(doi="10.1/x")
    assert out["openalex_cited_by"] == 10
    assert out["crossref_referenced_by"] == 8
    assert out["semanticscholar_influential"] == 2
    assert "error" in await server.get_citation_metrics()
