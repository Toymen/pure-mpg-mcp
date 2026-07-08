"""Offline tests for the individual enrichment provider connectors."""

from __future__ import annotations

import httpx
import pytest

from pure_mpg_mcp.enrichment import Enrichment

from fixtures_enrich import enrich_handler


async def test_fetch_combines_all_sources(enrich):
    out = await enrich.fetch("10.1/x", ["openalex", "crossref", "unpaywall", "semanticscholar", "bogus"])
    assert out["openalex"]["cited_by_count"] == 12
    assert out["openalex"]["institutions"] == ["MPI X"]
    assert out["crossref"]["container"] == "Journal of Tests"
    assert out["crossref"]["funders"] == ["DFG"]
    assert out["unpaywall"]["best_oa_pdf"] == "u.pdf"
    assert out["semanticscholar"]["tldr"] == "Short summary."
    assert "bogus" not in out


async def test_unpaywall_skipped_without_real_email(monkeypatch):
    monkeypatch.delenv("PURE_CONTACT_EMAIL", raising=False)
    e = Enrichment()
    e._client = httpx.AsyncClient(transport=httpx.MockTransport(enrich_handler))
    assert await e.unpaywall("10.1/x") is None
    await e.aclose()


async def test_missing_records_return_none(monkeypatch):
    monkeypatch.setenv("PURE_CONTACT_EMAIL", "real@mpg.de")
    e = Enrichment()
    e._client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    assert await e.openalex("10.1/x") is None
    assert await e.crossref("10.1/x") is None
    assert await e.unpaywall("10.1/x") is None
    assert await e.semanticscholar("10.1/x") is None
    assert await e.fetch("10.1/x", ["openalex"]) == {}
    await e.aclose()


async def test_get_json_swallows_http_errors():
    e = Enrichment()

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network")

    e._client = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    assert await e._get_json("https://api.openalex.org/works/x") is None
    await e.aclose()


@pytest.mark.network
async def test_openalex_live():
    e = Enrichment()
    try:
        out = await e.openalex("10.1126/science.1102896")
        assert out["cited_by_count"] > 1000
        assert out["topics"]
    finally:
        await e.aclose()
