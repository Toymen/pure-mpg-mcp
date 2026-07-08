"""Offline tests for organization/collection/feed tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server


async def test_org_collection_feed_and_info_tools():
    with (
        patch.object(server._client, "search_ous", new=AsyncMock(return_value={"n": 1})) as ous,
        patch.object(server._client, "ous_toplevel", new=AsyncMock(return_value={"roots": []})),
        patch.object(server._client, "search_contexts", new=AsyncMock(return_value={"n": 2})) as ctx,
        patch.object(server._client, "feed_recent", new=AsyncMock(return_value="<rss/>")),
        patch.object(server._client, "feed_open_access", new=AsyncMock(return_value="<oa/>")),
        patch.object(server._client, "service_info", new=AsyncMock(return_value={"status": "ok"})),
    ):
        assert await server.search_organizations(name="MPI") == {"n": 1}
        assert ous.call_args.kwargs["query"] == {"match": {"metadata.name": "MPI"}}
        assert await server.search_organizations() == {"n": 1}
        assert ous.call_args.kwargs["query"] == {"match_all": {}}
        assert await server.list_top_organizations() == {"roots": []}
        assert await server.search_collections(name="Journal") == {"n": 2}
        assert ctx.call_args.kwargs["query"] == {"match": {"name": "Journal"}}
        assert await server.search_collections() == {"n": 2}
        assert await server.recent_publications() == "<rss/>"
        assert await server.open_access_feed() == "<oa/>"
        assert await server.service_info() == {"status": "ok"}


async def test_organization_tree_navigation():
    with (
        patch.object(server._client, "get_ou", new=AsyncMock(return_value={"objectId": "ou_1"})),
        patch.object(server._client, "ous_firstlevel", new=AsyncMock(return_value=[{"objectId": "ou_2"}])),
        patch.object(server._client, "ou_children", new=AsyncMock(return_value=[{"objectId": "ou_3"}])),
        patch.object(server._client, "ou_id_path", new=AsyncMock(return_value=["ou_3", "ou_1"])),
        patch.object(server._client, "ou_name_path", new=AsyncMock(return_value=["Dept", "Institute"])),
    ):
        assert (await server.get_organization("ou_1"))["objectId"] == "ou_1"
        assert (await server.list_first_level_organizations())[0]["objectId"] == "ou_2"
        assert (await server.organization_children("ou_3"))[0]["objectId"] == "ou_3"
        hierarchy = await server.organization_hierarchy("ou_3")
    assert hierarchy == {"ouId": "ou_3", "idPath": ["ou_3", "ou_1"], "namePath": ["Dept", "Institute"]}


async def test_get_collection_and_extra_feeds():
    with (
        patch.object(server._client, "get_context", new=AsyncMock(return_value={"objectId": "ctx_1"})),
        patch.object(server._client, "feed_organization", new=AsyncMock(return_value="<rss>ou</rss>")),
        patch.object(server._client, "feed_search", new=AsyncMock(return_value="<rss>q</rss>")) as fs,
    ):
        assert (await server.get_collection("ctx_1"))["objectId"] == "ctx_1"
        assert await server.organization_feed("ou_1") == "<rss>ou</rss>"
        assert await server.search_feed("graphene") == "<rss>q</rss>"
    fs.assert_awaited_once_with("graphene")
