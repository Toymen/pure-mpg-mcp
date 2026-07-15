"""Opt-in live checks for organization/collection/feed critical MCP tools.

Run with:
    uv run --extra dev pytest -m network
"""

from __future__ import annotations

import pytest

from pure_mpg_mcp import server

from fixtures_live import LIVE_CONTEXT_ID, LIVE_OU_ID, assert_feed

pytestmark = [pytest.mark.network, pytest.mark.asyncio(loop_scope="session")]


async def test_live_organizations_collections_feeds_and_service_info():
    orgs = await server.search_organizations(name="Central Scientific Facility Materials", size=1)
    assert orgs["numberOfRecords"] >= 1

    org = await server.get_organization(LIVE_OU_ID)
    assert org["objectId"] == LIVE_OU_ID

    top = await server.list_top_organizations()
    first = await server.list_first_level_organizations()
    assert isinstance(top, list) and top
    assert isinstance(first, list) and first

    children = await server.organization_children(LIVE_OU_ID)
    hierarchy = await server.organization_hierarchy(LIVE_OU_ID)
    assert isinstance(children, list)
    assert hierarchy["idPath"][0] == LIVE_OU_ID
    assert "Max Planck" in hierarchy["namePath"][-1]

    collections = await server.search_collections(name="Publications of the MPI for Solar System Research", size=1)
    assert collections["numberOfRecords"] >= 1
    collection = await server.get_collection(LIVE_CONTEXT_ID)
    assert collection["objectId"] == LIVE_CONTEXT_ID

    assert_feed(await server.recent_publications())
    assert_feed(await server.open_access_feed())
    assert_feed(await server.organization_feed(LIVE_OU_ID))

    info = await server.service_info()
    assert info["status"] == "ok"
