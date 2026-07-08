"""Offline tests for ConeClient (the public CONE authority service)."""

from __future__ import annotations

import httpx

from pure_mpg_mcp.cone import ConeClient

from fixtures_pure import mock_transport


async def test_cone_query_persons(cone):
    out = await cone.query_persons("Doe")
    assert out[0]["id"] == "persons1"


async def test_cone_query_persons_non_json_returns_empty():
    c = ConeClient(base_url="https://pure.test/cone")
    mock_transport(c, lambda request: httpx.Response(200, text="<html/>"), base_url="https://pure.test/cone")
    async with c:
        assert await c.query_persons("Doe") == []


async def test_cone_resolve_person_cleans_record(cone):
    out = await cone.resolve_person("https://pure.test/cone/persons/resource/persons1/")
    assert out["personId"] == "persons1"
    assert out["givenName"] == "Jan"
    assert out["familyName"] == "Doe"
    assert out["orcid"] == "0000-0001-2345-6789"
    assert out["affiliation"] == "Max Planck Society, Some Institute"


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


async def test_cone_languages(cone):
    out = await cone.languages()
    assert {"id": "eng", "value": "English"} in out
    assert {"id": "deu", "value": "German"} in out


async def test_cone_languages_normalizes_resource_url_ids():
    c = ConeClient(base_url="https://pure.test/cone")
    mock_transport(
        c,
        lambda request: httpx.Response(
            200,
            json=[{"id": "https://pure.mpg.de/cone/iso639-3/resource/eng", "value": "eng - English"}],
        ),
        base_url="https://pure.test/cone",
    )
    async with c:
        assert await c.languages() == [{"id": "eng", "value": "eng - English"}]


async def test_cone_languages_non_json_returns_empty():
    c = ConeClient(base_url="https://pure.test/cone")
    mock_transport(c, lambda request: httpx.Response(200, text="<html/>"), base_url="https://pure.test/cone")
    async with c:
        assert await c.languages() == []
