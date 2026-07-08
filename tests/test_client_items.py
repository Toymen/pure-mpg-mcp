"""Offline HTTP-level tests for PureClient's /items endpoints."""

from __future__ import annotations

import httpx

from pure_mpg_mcp.client import PureClient

from fixtures_pure import mock_transport


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


async def test_scroll_get_export_and_component_endpoints(pure):
    assert (await pure.scroll_items("abc"))["scrollId"] == "abc"
    assert (await pure.get_item("item_1"))["objectId"] == "item_1"
    assert await pure.export_item("item_1") == "@article{key}"
    assert (await pure.get_component_metadata("item_1", "comp_1"))["visibility"] == "PUBLIC"


async def test_component_metadata_accepts_text_plain():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "text/plain"
        return httpx.Response(200, text="pdf:PDFVersion: 1.4\nX-TIKA:Parsed-By: parser\n")

    c = PureClient(base_url="https://pure.test/rest")
    mock_transport(c, handler)
    async with c:
        out = await c.get_component_metadata("item_1", "comp_1")
    assert out["pdf:PDFVersion"] == "1.4"
    assert out["X-TIKA:Parsed-By"] == "parser"


def test_component_content_and_thumbnail_urls():
    c = PureClient(base_url="https://pure.test/rest/")
    assert c.component_content_url("item_1", "comp_1") == "https://pure.test/rest/items/item_1/component/comp_1/content"
    assert (
        c.component_thumbnail_url("item_1", "comp_1")
        == "https://pure.test/rest/items/item_1/component/comp_1/thumbnail"
    )


async def test_export_search_posts_format_and_citation_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/items/search"
        assert dict(request.url.params) == {
            "format": "json_citation", "citation": "APA", "cslConeId": "csl_1",
        }
        return httpx.Response(200, text="citation text")

    c = PureClient(base_url="https://pure.test/rest")
    mock_transport(c, handler)
    async with c:
        out = await c.export_search(
            {"match_all": {}}, format="json_citation", citation="APA", csl_cone_id="csl_1",
        )
    assert out == "citation text"


async def test_find_by_doi_strips_url_prefix(pure):
    out = await pure.find_by_doi("https://doi.org/10.1/x ")
    should = out["echo"]["query"]["bool"]["should"]
    assert {"term": {"metadata.identifiers.id.keyword": "10.1/x"}} in should


async def test_count_items_uses_size_zero(pure):
    assert await pure.count_items({"match_all": {}}) == 1
