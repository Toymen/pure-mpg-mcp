"""Offline tests for the per-provider research-data discovery connectors."""

from __future__ import annotations

import httpx
import pytest

from pure_mpg_mcp.datasets import DOI_SOURCES, ORCID_SOURCES, Datasets, normalize_orcid

from fixtures_datasets import ARTICLE_DOI


def test_normalize_orcid():
    assert normalize_orcid("0000-0003-1419-2405") == "0000-0003-1419-2405"
    assert normalize_orcid("https://orcid.org/0000-0003-1419-2405/") == "0000-0003-1419-2405"
    assert normalize_orcid("0000-0002-1825-009X") == "0000-0002-1825-009X"
    assert normalize_orcid("not-an-orcid") is None


async def test_by_doi_combines_all_sources(datasets):
    out = await datasets.by_doi(ARTICLE_DOI, list(DOI_SOURCES) + ["bogus"])
    assert set(out) == set(DOI_SOURCES)
    assert {h["doi"] for h in out["scholexplorer"]} == {"10.5061/dryad.abc", "10.21233/ms5z-v475"}
    assert out["datacite"][0]["doi"] == "10.6084/m9.figshare.32996252"
    assert out["datacite"][0]["relation"] == "IsSupplementTo"
    assert out["b2find"][0]["doi"] == "10.1594/pangaea.867908"
    assert out["b2find"][0]["publisher"] == "PANGAEA"
    assert out["crossref"] == [
        {"doi": "10.1107/xyz/supp1", "title": None, "publisher": None, "year": None,
         "relation": "is-supplemented-by"}
    ]
    assert out["zenodo"][0]["doi"] == "10.5281/zenodo.111"
    assert out["zenodo"][0]["year"] == 2020
    assert out["figshare"][0]["title"] == "S1 Table"


async def test_scholexplorer_direction_relations(datasets):
    hits = await datasets.scholexplorer(ARTICLE_DOI)
    by_doi = {h["doi"]: h for h in hits}
    assert by_doi["10.21233/ms5z-v475"]["relation"] == "IsSupplementTo"
    assert by_doi["10.21233/ms5z-v475"]["publisher"] == "Unknown Repository"
    assert by_doi["10.5061/dryad.abc"]["relation"] == "References"


async def test_dryad_keeps_only_hits_related_to_the_doi(datasets):
    hits = await datasets.dryad(ARTICLE_DOI)
    assert [h["doi"] for h in hits] == ["10.5061/dryad.7rh4625"]
    assert hits[0]["year"] == 2018


async def test_by_orcid_combines_all_sources(datasets):
    out = await datasets.by_orcid("https://orcid.org/0000-0003-1419-2405", list(ORCID_SOURCES))
    assert set(out) == set(ORCID_SOURCES)
    assert out["datacite"][0]["doi"] == "10.6084/m9.figshare.821213.v1"
    assert out["openaire"][0]["doi"] == "10.6084/m9.figshare.107019.v2"
    assert out["openalex"][0]["doi"] == "10.5281/zenodo.333"
    assert out["openalex"][0]["year"] == 2022
    assert out["zenodo"][0]["doi"] == "10.5281/zenodo.222"
    assert out["figshare"][0]["doi"] == "10.6084/m9.figshare.6"


async def test_errors_return_none_and_are_omitted():
    d = Datasets()
    d._client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert await d.scholexplorer("10.1/x") is None
    assert await d.datacite_by_orcid("0000-0003-1419-2405") is None
    assert await d.by_doi("10.1/x", ["datacite", "crossref"]) == {}
    await d.aclose()


async def test_empty_results_are_kept_as_empty_lists():
    def nothing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "meta": {"total": 0}})

    d = Datasets()
    d._client = httpx.AsyncClient(transport=httpx.MockTransport(nothing))
    out = await d.by_doi("10.1/x", ["datacite"])
    assert out == {"datacite": []}  # queried fine, no data found — meaningful answer
    await d.aclose()


@pytest.mark.network
async def test_scholexplorer_live_finds_supplement():
    d = Datasets()
    try:
        hits = await d.scholexplorer("10.1016/j.quascirev.2014.09.022")
        assert any(h["relation"] == "IsSupplementTo" for h in hits)
    finally:
        await d.aclose()


@pytest.mark.network
async def test_datacite_by_orcid_live():
    d = Datasets()
    try:
        hits = await d.datacite_by_orcid("0000-0003-1419-2405")
        assert len(hits) > 5
        assert all(h["doi"] for h in hits)
    finally:
        await d.aclose()


@pytest.mark.network
async def test_datacite_by_doi_live_finds_supplement():
    d = Datasets()
    try:
        hits = await d.datacite_by_doi("10.1159/000553587")
        assert any(h["relation"] == "IsSupplementTo" for h in hits)
    finally:
        await d.aclose()


@pytest.mark.network
async def test_b2find_live_finds_pangaea_doi():
    d = Datasets()
    try:
        hits = await d.b2find("10.1594/pangaea.867908")
        assert any((h["doi"] or "").lower() == "10.1594/pangaea.867908" for h in hits)
    finally:
        await d.aclose()


@pytest.mark.network
async def test_openaire_by_orcid_live():
    d = Datasets()
    try:
        hits = await d.openaire_by_orcid("0000-0003-1419-2405")
        assert len(hits) > 5
        assert any(h["doi"] for h in hits)
    finally:
        await d.aclose()
