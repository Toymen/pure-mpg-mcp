"""Offline tests for lookup/authority tools: DOI, author resolution, languages."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server

from helpers import _search_payload


async def test_find_by_doi_summarizes():
    with patch.object(server._client, "find_by_doi", new=AsyncMock(return_value=_search_payload("item_4"))):
        out = await server.find_by_doi("10.1/x")
    assert out["items"][0]["itemId"] == "item_4"


async def test_resolve_author_paths():
    with (
        patch.object(server._cone, "resolve_person", new=AsyncMock(return_value={"personId": "p1"})),
        patch.object(server._cone, "query_persons", new=AsyncMock(return_value=[{"id": "p1"}])),
    ):
        assert (await server.resolve_author(person_id="p1"))["personId"] == "p1"
        named = await server.resolve_author(name="Planck")
        assert named == {"query": "Planck", "candidates": [{"id": "p1"}]}
    assert "error" in await server.resolve_author()


async def test_author_publications_paths():
    mock = AsyncMock(return_value=_search_payload("item_5"))
    with patch.object(server._client, "search_items", new=mock):
        await server.author_publications(person_id="https://pure.mpg.de/cone/persons/resource/persons1/")
        q = mock.call_args.kwargs["query"]
        assert q == {"match": {"metadata.creators.person.identifier.id": "/persons/resource/persons1"}}
        await server.author_publications(name="Planck")
        assert mock.call_args.kwargs["query"] == {"match": {"metadata.creators.person.familyName": "Planck"}}
    assert "error" in await server.author_publications()


async def test_language_codes_falls_back_when_cone_unreachable():
    with patch.object(server._cone, "languages", new=AsyncMock(side_effect=RuntimeError("down"))):
        codes = await server._language_codes()
    assert codes == server._LANGUAGES


async def test_language_codes_falls_back_on_empty_cone_response():
    with patch.object(server._cone, "languages", new=AsyncMock(return_value=[])):
        codes = await server._language_codes()
    assert codes == server._LANGUAGES


async def test_language_codes_uses_live_cone_vocabulary():
    entries = [{"id": "eng", "value": "English"}, {"id": "deu", "value": "German"}, {"id": "", "value": "empty"}]
    with patch.object(server._cone, "languages", new=AsyncMock(return_value=entries)):
        codes = await server._language_codes()
    assert codes == ["deu", "eng"]


async def test_list_languages_tool():
    entries = [{"id": "eng", "value": "English"}]
    with patch.object(server._cone, "languages", new=AsyncMock(return_value=entries)):
        out = await server.list_languages()
    assert out == {"languages": entries}
