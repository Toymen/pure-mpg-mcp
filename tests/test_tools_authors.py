"""Offline tests for coauthorship_analysis and analyze_authors tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server

from helpers import _authored_record, _record_with_creators


async def test_coauthorship_analysis():
    recs = [_record_with_creators("MPI A")]
    with patch.object(server._client, "fetch_all", new=AsyncMock(return_value=recs)):
        out = await server.coauthorship_analysis()
    assert out["analyzedRecords"] == 1
    assert out["soloAuthored"] == 1


async def test_analyze_authors_enriches_initials_via_cone():
    rec = _authored_record("J.", "/persons/resource/persons9")
    resolved = {"givenName": "Jan", "orcid": "0000-0001-2345-6789", "affiliation": "MPI X"}
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value=rec)),
        patch.object(server._cone, "resolve_person", new=AsyncMock(return_value=resolved)),
    ):
        out = await server.analyze_authors(item_id="item_a")
    author = out["authors"][0]
    assert author["firstName"] == "Jan"
    assert author["orcid"] == "0000-0001-2345-6789"
    assert author["affiliation"] == "MPI X"
    assert out["summary"]["withOrcid"] == 1


async def test_analyze_authors_survives_cone_failure_and_query_path():
    rec = _authored_record("J.", "/persons/resource/persons9")
    with (
        patch.object(server._client, "fetch_all", new=AsyncMock(return_value=[rec])),
        patch.object(server._cone, "resolve_person", new=AsyncMock(side_effect=RuntimeError("down"))),
    ):
        out = await server.analyze_authors()
    assert out["authors"][0]["firstName"] is None
    assert out["summary"]["analyzedRecords"] == 1
