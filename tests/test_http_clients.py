"""Offline HTTP-level tests for PureClient, ConeClient, and Enrichment.

Each client's internal httpx.AsyncClient is swapped for one backed by
httpx.MockTransport, so real request/response handling (paths, params,
JSON decoding, error fallbacks) is exercised without any network.
"""

import json

import httpx
import pytest

from pure_mpg_mcp.client import PureClient
from pure_mpg_mcp.cone import ConeClient
from pure_mpg_mcp.enrichment import Enrichment, contact_email, normalize_doi, unavailable_sources


def _mock(client_holder, handler, base_url="https://pure.test/rest"):
    client_holder._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=base_url)


# --- PureClient -----------------------------------------------------------


def _pure_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/rest/items/search":
        body = json.loads(request.content)
        return httpx.Response(200, json={"numberOfRecords": 1, "records": [], "echo": body})
    if path == "/rest/items/search/scroll":
        return httpx.Response(200, json={"scrollId": request.url.params["scrollId"], "records": []})
    if path == "/rest/items/item_1":
        return httpx.Response(200, json={"objectId": "item_1"})
    if path == "/rest/items/item_1/export":
        return httpx.Response(200, text="@article{key}")
    if path == "/rest/items/item_1/component/comp_1/metadata":
        return httpx.Response(200, json={"visibility": "PUBLIC"})
    if path == "/rest/ous/search":
        return httpx.Response(200, json={"numberOfRecords": 2})
    if path == "/rest/ous/ou_1":
        return httpx.Response(200, json={"objectId": "ou_1"})
    if path == "/rest/ous/toplevel":
        return httpx.Response(200, json=[{"objectId": "ou_root"}])
    if path == "/rest/contexts/search":
        return httpx.Response(200, json={"numberOfRecords": 3})
    if path == "/rest/feed/recent":
        return httpx.Response(200, text="<rss>recent</rss>")
    if path == "/rest/feed/oa":
        return httpx.Response(200, text="<rss>oa</rss>")
    if path == "/rest/miscellaneous/serviceInfo":
        return httpx.Response(200, text="")
    return httpx.Response(404)


@pytest.fixture
async def pure() -> PureClient:
    c = PureClient(base_url="https://pure.test/rest")
    _mock(c, _pure_handler)
    async with c:
        yield c


async def test_search_items_posts_query_with_sort_and_search_after(pure):
    out = await pure.search_items(
        query={"match_all": {}}, size=5, from_=2,
        sort=[{"f": {"order": "asc"}}], search_after=["cursor"],
    )
    echo = out["echo"]
    assert echo == {
        "query": {"match_all": {}}, "size": 5, "from": 2,
        "sort": [{"f": {"order": "asc"}}], "search_after": ["cursor"],
    }


async def test_scroll_get_export_component_and_misc_endpoints(pure):
    assert (await pure.scroll_items("abc"))["scrollId"] == "abc"
    assert (await pure.get_item("item_1"))["objectId"] == "item_1"
    assert await pure.export_item("item_1") == "@article{key}"
    assert (await pure.get_component_metadata("item_1", "comp_1"))["visibility"] == "PUBLIC"
    assert (await pure.search_ous({"match_all": {}}))["numberOfRecords"] == 2
    assert (await pure.get_ou("ou_1"))["objectId"] == "ou_1"
    assert (await pure.ous_toplevel())[0]["objectId"] == "ou_root"
    assert (await pure.search_contexts({"match_all": {}}))["numberOfRecords"] == 3
    assert "recent" in await pure.feed_recent()
    assert "oa" in await pure.feed_open_access()


async def test_find_by_doi_strips_url_prefix(pure):
    out = await pure.find_by_doi("https://doi.org/10.1/x ")
    should = out["echo"]["query"]["bool"]["should"]
    assert {"term": {"metadata.identifiers.id.keyword": "10.1/x"}} in should


async def test_count_items_uses_size_zero(pure):
    assert await pure.count_items({"match_all": {}}) == 1


async def test_service_info_empty_json_and_raw_bodies():
    responses = iter([
        httpx.Response(200, text=""),
        httpx.Response(200, json={"version": "1.0"}),
        httpx.Response(200, text="plain text"),
    ])
    c = PureClient(base_url="https://pure.test/rest")
    _mock(c, lambda request: next(responses))
    async with c:
        empty = await c.service_info()
        assert empty["detail"].startswith("empty")
        assert (await c.service_info())["version"] == "1.0"
        raw = await c.service_info()
        assert raw["raw"] == "plain text"


async def test_get_raises_on_http_error():
    c = PureClient(base_url="https://pure.test/rest")
    _mock(c, lambda request: httpx.Response(500))
    async with c:
        with pytest.raises(httpx.HTTPStatusError):
            await c.get_item("item_1")


def test_base_url_env_fallback(monkeypatch):
    monkeypatch.setenv("PURE_BASE_URL", "https://env.test/rest/")
    assert PureClient().base_url == "https://env.test/rest"


# --- ConeClient -----------------------------------------------------------

_CONE_PERSON = {
    "http://x/givenname": "Jan",
    "http://x/family_name": "Doe",
    "http://x/title": "Doe, Jan",
    "http://x/identifier": "https://orcid.org/0000-0001-2345-6789",
    "http://x/position": {"organization": "Max Planck Society, Some Institute"},
}


def _cone_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/cone/persons/query":
        return httpx.Response(200, json=[{"id": "persons1", "type": "main", "value": "Doe, Jan"}])
    if request.url.path == "/cone/persons/resource/persons1":
        return httpx.Response(200, json=_CONE_PERSON)
    return httpx.Response(404)


@pytest.fixture
async def cone() -> ConeClient:
    c = ConeClient(base_url="https://pure.test/cone")
    _mock(c, _cone_handler, base_url="https://pure.test/cone")
    async with c:
        yield c


async def test_cone_query_persons(cone):
    out = await cone.query_persons("Doe")
    assert out[0]["id"] == "persons1"


async def test_cone_query_persons_non_json_returns_empty():
    c = ConeClient(base_url="https://pure.test/cone")
    _mock(c, lambda request: httpx.Response(200, text="<html/>"), base_url="https://pure.test/cone")
    async with c:
        assert await c.query_persons("Doe") == []


async def test_cone_resolve_person_cleans_record(cone):
    out = await cone.resolve_person("https://pure.test/cone/persons/resource/persons1/")
    assert out["personId"] == "persons1"
    assert out["givenName"] == "Jan"
    assert out["familyName"] == "Doe"
    assert out["orcid"] == "0000-0001-2345-6789"
    assert out["affiliation"] == "Max Planck Society, Some Institute"


# --- Enrichment -----------------------------------------------------------


def test_normalize_doi_variants():
    assert normalize_doi(" https://doi.org/10.1/x ") == "10.1/x"
    assert normalize_doi("doi:10.1/x") == "10.1/x"
    assert normalize_doi("10.1/x") == "10.1/x"


def test_contact_email_and_unavailable_sources(monkeypatch):
    monkeypatch.setenv("PURE_CONTACT_EMAIL", "someone@example.com")
    assert contact_email() is None
    assert "unpaywall" in unavailable_sources(["unpaywall"])
    monkeypatch.setenv("PURE_CONTACT_EMAIL", "real@mpg.de")
    assert contact_email() == "real@mpg.de"
    assert unavailable_sources(["unpaywall"]) == {}


_OPENALEX = {
    "id": "https://openalex.org/W1",
    "cited_by_count": 12,
    "open_access": {"oa_status": "gold"},
    "topics": [{"display_name": "Physics"}],
    "authorships": [{"institutions": [{"display_name": "MPI X", "ror": "https://ror.org/r1"}]}],
    "referenced_works": ["W2"],
    "related_works": ["W3"],
}

_CROSSREF = {
    "message": {
        "is-referenced-by-count": 8,
        "references-count": 30,
        "funder": [{"name": "DFG"}],
        "license": [{"URL": "https://cc.org/by"}],
        "publisher": "ACS",
        "container-title": ["Journal of Tests"],
    }
}

_UNPAYWALL = {
    "is_oa": True,
    "oa_status": "green",
    "best_oa_location": {"url": "u", "url_for_pdf": "u.pdf", "host_type": "repository", "license": "cc-by"},
}

_S2 = {
    "citationCount": 9,
    "influentialCitationCount": 2,
    "fieldsOfStudy": ["Physics"],
    "tldr": {"text": "Short summary."},
}


def _enrich_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "api.openalex.org":
        return httpx.Response(200, json=_OPENALEX)
    if host == "api.crossref.org":
        return httpx.Response(200, json=_CROSSREF)
    if host == "api.unpaywall.org":
        return httpx.Response(200, json=_UNPAYWALL)
    if host == "api.semanticscholar.org":
        return httpx.Response(200, json=_S2)
    return httpx.Response(404)


@pytest.fixture
async def enrich(monkeypatch) -> Enrichment:
    monkeypatch.setenv("PURE_CONTACT_EMAIL", "real@mpg.de")
    e = Enrichment()
    e._client = httpx.AsyncClient(transport=httpx.MockTransport(_enrich_handler))
    yield e
    await e.aclose()


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
    e._client = httpx.AsyncClient(transport=httpx.MockTransport(_enrich_handler))
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
