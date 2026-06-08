"""Offline unit tests for the analysis, gender-cleaning, and CONE parsing logic."""

import pytest

from pure_mpg_mcp import analysis
from pure_mpg_mcp.cone import ConeClient
from pure_mpg_mcp.enrichment import Enrichment, normalize_doi
from pure_mpg_mcp.gender import clean_given_name

REC = {
    "data": {
        "objectId": "item_1",
        "metadata": {
            "genre": "ARTICLE",
            "languages": ["eng"],
            "datePublishedInPrint": "2021-03-01",
            "creators": [
                {
                    "role": "AUTHOR",
                    "person": {
                        "givenName": "Jan",
                        "familyName": "Stelzner",
                        "organizations": [{"name": "Max Planck Institute X"}],
                    },
                },
                {
                    "role": "AUTHOR",
                    "person": {
                        "givenName": "V.",
                        "familyName": "Meyer",
                        "organizations": [{"name": "Universität Hamburg"}],
                    },
                },
            ],
        },
        "files": [{"metadata": {"visibility": "PUBLIC"}}],
    }
}


def test_year_and_open_access():
    assert analysis._year(REC) == "2021"
    assert analysis.is_open_access(REC) is True


def test_distribution_genre_and_org():
    d = analysis.distribution([REC], group_by="genre")
    assert d["buckets"][0] == {"key": "ARTICLE", "count": 1}
    orgs = analysis.distribution([REC], group_by="organization")
    names = {b["key"] for b in orgs["buckets"]}
    assert "Max Planck Institute X" in names


def test_coauthorship_team_size():
    c = analysis.coauthorship([REC])
    assert c["averageAuthorsPerPublication"] == 2.0
    assert c["soloAuthored"] == 0


def test_summarize_gender_threshold():
    authors = [
        {"gender": "male", "probability": 0.99},
        {"gender": "female", "probability": 0.55},  # below threshold -> unknown
        {"gender": None, "probability": None},
    ]
    s = analysis.summarize_gender(authors, threshold=0.6)
    assert s["male"] == 1
    assert s["female"] == 0
    assert s["unknown"] == 2


def test_clean_given_name():
    assert clean_given_name("Jan") == "Jan"
    assert clean_given_name("J.") is None
    assert clean_given_name("J") is None
    assert clean_given_name("Anne-Marie") == "Anne"
    assert clean_given_name("") is None
    assert clean_given_name(None) is None


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1/x") == "10.1/x"
    assert normalize_doi("doi:10.1/x") == "10.1/x"
    assert normalize_doi("  10.1/x ") == "10.1/x"


async def test_enrichment_fetch_skips_unknown_and_missing(monkeypatch):
    e = Enrichment()
    try:
        async def fake_openalex(doi):
            return {"cited_by_count": 42}

        async def fake_crossref(doi):
            return None  # source has no record -> omitted

        monkeypatch.setattr(e, "openalex", fake_openalex)
        monkeypatch.setattr(e, "crossref", fake_crossref)
        out = await e.fetch("10.1/x", ["openalex", "crossref", "bogus"])
        assert out == {"openalex": {"cited_by_count": 42}}
    finally:
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


def test_cone_clean_person():
    raw = {
        "http_xmlns_com_foaf_0_1_givenname": "Jan",
        "http_xmlns_com_foaf_0_1_family_name": "Stelzner",
        "http_purl_org_dc_elements_1_1_title": "Stelzner, Jan",
        "some_orcid_field": "0000-0002-1825-0097",
    }
    out = ConeClient._clean_person("persons314810", raw)
    assert out["givenName"] == "Jan"
    assert out["familyName"] == "Stelzner"
    assert out["orcid"] == "0000-0002-1825-0097"
