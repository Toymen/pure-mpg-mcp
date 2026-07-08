"""Offline tests for enrichment config helpers and source dispatch."""

from __future__ import annotations

from pure_mpg_mcp.enrichment import Enrichment, contact_email, normalize_doi, unavailable_sources


def test_normalize_doi_variants():
    assert normalize_doi(" https://doi.org/10.1/x ") == "10.1/x"
    assert normalize_doi("doi:10.1/x") == "10.1/x"
    assert normalize_doi("10.1/x") == "10.1/x"


def test_contact_email_and_unavailable_sources(monkeypatch):
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
