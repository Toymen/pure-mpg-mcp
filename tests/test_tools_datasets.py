"""Offline tests for research-data discovery MCP tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server

from helpers import _item_with_doi


async def test_find_research_data_rejects_unknown_source():
    out = await server.find_research_data(doi="10.1/x", sources=["datacite", "nope"])
    assert "unknown source(s)" in out["error"]
    assert "datacite" in out["available"]


async def test_find_research_data_requires_doi():
    with patch.object(server._client, "get_item", new=AsyncMock(return_value=_item_with_doi(None))):
        out = await server.find_research_data(item_id="item_d")
    assert out["error"] == "no DOI available for this publication"


async def test_find_research_data_from_item_merges_and_deduplicates_hits():
    by_source = {
        "datacite": [
            {
                "doi": "10.5061/dryad.abc",
                "title": "Dataset",
                "publisher": "Dryad",
                "year": 2020,
                "relation": "IsSupplementTo",
            }
        ],
        "scholexplorer": [
            {
                "doi": "10.5061/dryad.abc",
                "title": "Dataset via Scholix",
                "publisher": "Dryad",
                "year": None,
                "relation": "IsSupplementTo",
            },
            {"doi": None, "title": "Supplement table", "publisher": "figshare", "year": 2021, "relation": None},
        ],
    }
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value=_item_with_doi("10.1/x"))),
        patch.object(server._datasets, "by_doi", new=AsyncMock(return_value=by_source)) as by_doi,
    ):
        out = await server.find_research_data(item_id="item_d", sources=["datacite", "scholexplorer"])

    by_doi.assert_awaited_once_with("10.1/x", ["datacite", "scholexplorer"])
    assert out["pure"]["itemId"] == "item_d"
    assert out["doi"] == "10.1/x"
    assert out["hasResearchData"] is True
    assert out["sourcesReturned"] == ["datacite", "scholexplorer"]
    assert len(out["datasets"]) == 2
    assert out["datasets"][0]["doi"] == "10.5061/dryad.abc"
    assert out["datasets"][0]["sources"] == ["datacite", "scholexplorer"]
    assert out["datasets"][1]["title"] == "Supplement table"
    assert "datasetsearch.research.google.com" in out["googleDatasetSearchUrl"]


async def test_find_research_data_by_orcid_normalizes_and_merges():
    by_source = {
        "datacite": [{"doi": "10.5281/zenodo.1", "title": "A", "publisher": "Zenodo", "year": 2022, "relation": None}],
        "openalex": [{"doi": "https://doi.org/10.5281/zenodo.1", "title": "A", "publisher": None, "year": 2022, "relation": None}],
    }
    with patch.object(server._datasets, "by_orcid", new=AsyncMock(return_value=by_source)) as by_orcid:
        out = await server.find_research_data_by_orcid(
            "https://orcid.org/0000-0003-1419-2405/", sources=["datacite", "openalex"]
        )

    by_orcid.assert_awaited_once_with("0000-0003-1419-2405", ["datacite", "openalex"])
    assert out["orcid"] == "0000-0003-1419-2405"
    assert out["hasResearchData"] is True
    assert len(out["datasets"]) == 1
    assert out["datasets"][0]["sources"] == ["datacite", "openalex"]


async def test_find_research_data_by_orcid_rejects_invalid_orcid():
    out = await server.find_research_data_by_orcid("not-an-orcid")
    assert out["error"] == "invalid ORCID"
