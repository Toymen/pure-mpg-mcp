"""Offline tests for the find_full_text tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server

from helpers import _item_with_doi


async def test_find_full_text_prefers_pure_files_then_unpaywall():
    up = {"unpaywall": {"is_oa": True, "oa_status": "gold", "best_oa_pdf": "u.pdf", "best_oa_url": "u"}}
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value=_item_with_doi("10.1/x"))),
        patch.object(server._enrich, "fetch", new=AsyncMock(return_value=up)),
    ):
        out = await server.find_full_text(item_id="item_d")
    assert out["purePublicFiles"] == [{"componentId": "comp_1", "name": "paper.pdf", "license": None}]
    assert out["isOpenAccess"] is True
    assert out["bestFreePdf"] == "u.pdf"


async def test_find_full_text_reads_root_file_visibility():
    item = _item_with_doi("10.1/x")
    item["files"][0]["metadata"].pop("visibility", None)
    item["files"][0]["visibility"] = "PUBLIC"
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value=item)),
        patch.object(server._enrich, "fetch", new=AsyncMock(return_value={})),
    ):
        out = await server.find_full_text(item_id="item_d")
    assert out["purePublicFiles"] == [{"componentId": "comp_1", "name": "paper.pdf", "license": None}]
    assert out["isOpenAccess"] is True


async def test_find_full_text_without_doi():
    out = await server.find_full_text()
    assert out == {"doi": None, "purePublicFiles": [], "isOpenAccess": False}
