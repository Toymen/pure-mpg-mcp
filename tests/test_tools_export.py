"""Offline tests for export/get_publication/file-metadata tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server


async def test_get_publication_export_and_file_metadata():
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value={"objectId": "item_3"})),
        patch.object(server._client, "export_item", new=AsyncMock(return_value="@article{...}")),
        patch.object(server._client, "get_component_metadata", new=AsyncMock(return_value={"f": 1})),
    ):
        assert (await server.get_publication("item_3"))["objectId"] == "item_3"
        assert (await server.export_publication("item_3")).startswith("@article")
        out = await server.get_file_metadata("item_3", "comp_1")
    assert out["f"] == 1
    assert out["contentUrl"].endswith("/items/item_3/component/comp_1/content")
    assert out["thumbnailUrl"].endswith("/items/item_3/component/comp_1/thumbnail")


async def test_export_search_results_defaults_and_overrides():
    mock = AsyncMock(return_value="@article{a}\n@article{b}")
    with patch.object(server._client, "export_search", new=mock):
        out = await server.export_search_results(format="BibTex", size=50)
    assert out.startswith("@article")
    assert mock.call_args.kwargs["query"] == {"match_all": {}}
    assert mock.call_args.kwargs["format"] == "BibTex"
    assert mock.call_args.kwargs["size"] == 50
