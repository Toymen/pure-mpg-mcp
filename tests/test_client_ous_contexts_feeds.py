"""Offline HTTP-level tests for PureClient's /ous, /contexts, /feed, and service-info endpoints."""

from __future__ import annotations

import httpx

from pure_mpg_mcp.client import PureClient

from fixtures_pure import mock_transport


async def test_ous_search_get_and_toplevel(pure):
    assert (await pure.search_ous({"match_all": {}}))["numberOfRecords"] == 2
    assert (await pure.get_ou("ou_1"))["objectId"] == "ou_1"
    assert (await pure.ous_toplevel())[0]["objectId"] == "ou_root"


async def test_contexts_search_and_recent_feeds(pure):
    assert (await pure.search_contexts({"match_all": {}}))["numberOfRecords"] == 3
    assert "recent" in await pure.feed_recent()
    assert "oa" in await pure.feed_open_access()


async def test_organization_tree_and_context_and_extra_feeds(pure):
    assert (await pure.ous_firstlevel())[0]["objectId"] == "ou_first"
    assert (await pure.ou_children("ou_1"))[0]["objectId"] == "ou_child"
    assert await pure.ou_id_path("ou_1") == ["ou_1", "ou_root"]
    assert await pure.ou_name_path("ou_1") == ["Dept", "Institute"]
    assert (await pure.get_context("ctx_1"))["objectId"] == "ctx_1"
    assert "ou" in await pure.feed_organization("ou_1")
    assert "graphene" in await pure.feed_search("graphene")


async def test_text_plain_organization_paths_are_split_into_lists():
    responses = iter([
        httpx.Response(200, text="ou_1,ou_root"),
        httpx.Response(200, text="Dept, Institute"),
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "text/plain"
        return next(responses)

    c = PureClient(base_url="https://pure.test/rest")
    mock_transport(c, handler)
    async with c:
        assert await c.ou_id_path("ou_1") == ["ou_1", "ou_root"]
        assert await c.ou_name_path("ou_1") == ["Dept", "Institute"]


async def test_feeds_request_xml_compatible_accept_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "application/atom+xml" in request.headers["accept"]
        return httpx.Response(200, text="<feed/>")

    c = PureClient(base_url="https://pure.test/rest")
    mock_transport(c, handler)
    async with c:
        assert await c.feed_recent() == "<feed/>"
        assert await c.feed_open_access() == "<feed/>"
        assert await c.feed_organization("ou_1") == "<feed/>"
        assert await c.feed_search("graphene") == "<feed/>"


async def test_service_info_empty_json_and_raw_bodies():
    responses = iter([
        httpx.Response(200, text=""),
        httpx.Response(200, json={"version": "1.0"}),
        httpx.Response(200, text="plain text"),
    ])
    c = PureClient(base_url="https://pure.test/rest")
    mock_transport(c, lambda request: next(responses))
    async with c:
        empty = await c.service_info()
        assert empty["detail"].startswith("empty")
        assert (await c.service_info())["version"] == "1.0"
        raw = await c.service_info()
        assert raw["raw"] == "plain text"
