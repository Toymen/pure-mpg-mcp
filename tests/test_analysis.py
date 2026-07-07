"""Offline unit tests for the analysis, name-cleaning, and CONE parsing logic."""

import pytest

from pure_mpg_mcp import analysis
from pure_mpg_mcp.analysis import clean_given_name
from pure_mpg_mcp.cone import ConeClient
from pure_mpg_mcp.enrichment import Enrichment, contact_email, normalize_doi, unavailable_sources

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
        "files": [{"visibility": "PUBLIC", "metadata": {}}],
    }
}


def test_year_and_open_access():
    assert analysis._year(REC) == "2021"
    assert analysis.is_open_access(REC) is True


def test_closed_access_locator_is_not_open_access():
    """A PUBLIC-visibility locator pointing at a paywalled page must not count as OA."""
    locator_only = {"data": {"files": [{"visibility": "PUBLIC", "oaStatus": "CLOSED_ACCESS", "metadata": {}}]}}
    assert analysis.is_open_access(locator_only) is False

    mixed = {
        "data": {
            "files": [
                {"visibility": "PUBLIC", "oaStatus": "CLOSED_ACCESS", "metadata": {}},
                {"visibility": "PUBLIC", "oaStatus": "GOLD", "metadata": {}},
            ]
        }
    }
    assert analysis.is_open_access(mixed) is True


def test_creators_includes_editors_by_default():
    rec = {
        "data": {
            "metadata": {
                "creators": [
                    {"role": "EDITOR", "person": {"familyName": "Editorson"}},
                    {"role": "AUTHOR", "person": {"familyName": "Authorman"}},
                    {"role": "TRANSLATOR", "person": {"familyName": "Translated"}},
                ]
            }
        }
    }
    names = {p["familyName"] for p in analysis.creators(rec)}
    assert names == {"Editorson", "Authorman"}
    assert {p["familyName"] for p in analysis.creators(rec, roles=("AUTHOR",))} == {"Authorman"}
    assert {p["familyName"] for p in analysis.creators(rec, roles=None)} == {
        "Editorson", "Authorman", "Translated",
    }


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


def test_contact_email_and_unavailable(monkeypatch):
    monkeypatch.delenv("PURE_CONTACT_EMAIL", raising=False)
    assert contact_email() is None
    assert "unpaywall" in unavailable_sources(["unpaywall", "openalex"])
    assert unavailable_sources(["openalex"]) == {}

    monkeypatch.setenv("PURE_CONTACT_EMAIL", "anybody@example.com")  # example.com == unset
    assert contact_email() is None

    monkeypatch.setenv("PURE_CONTACT_EMAIL", "me@inst.edu")
    assert contact_email() == "me@inst.edu"
    assert unavailable_sources(["unpaywall"]) == {}


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
