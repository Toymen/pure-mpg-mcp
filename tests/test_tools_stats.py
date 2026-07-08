"""Offline tests for the publication_statistics tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pure_mpg_mcp import server

from helpers import _dated_record, _record_with_creators, _year_of_filter


async def test_publication_statistics_year_counts_each_year():
    counts = {"2019": 2, "2020": 0, "2021": 5}

    async def count_items(query):
        return counts[_year_of_filter(query)]

    # bounds order: print-asc, print-desc, online-asc, online-desc
    search = AsyncMock(
        side_effect=[
            _dated_record("metadata.datePublishedInPrint", "2019-03-01"),
            _dated_record("metadata.datePublishedInPrint", "2020-01-01"),
            _dated_record("metadata.datePublishedOnline", "2020-06-01"),
            _dated_record("metadata.datePublishedOnline", "2021-11-30"),
        ]
    )
    with (
        patch.object(server._client, "search_items", new=search),
        patch.object(server._client, "count_items", new=AsyncMock(side_effect=count_items)),
    ):
        out = await server.publication_statistics(group_by="year")
    assert out["totalMatchingRecords"] == 7
    assert out["buckets"] == [{"key": "2019", "count": 2}, {"key": "2021", "count": 5}]


async def test_publication_statistics_year_fallback_when_no_dates():
    empty = {"numberOfRecords": 0, "records": []}
    with (
        patch.object(server._client, "search_items", new=AsyncMock(side_effect=[empty, empty, empty, empty])),
        patch.object(server._client, "count_items", new=AsyncMock(return_value=0)),
    ):
        out = await server.publication_statistics(group_by="year")
    assert out["buckets"] == []


async def test_publication_statistics_genre_and_language():
    async def count_items(query):
        clause = query["bool"]["filter"][0]["term"]
        val = next(iter(clause.values()))
        return {"ARTICLE": 7, "BOOK": 3, "eng": 9, "deu": 4}.get(val, 0)

    cone_langs = AsyncMock(return_value=[{"id": "eng", "value": "English"}, {"id": "deu", "value": "German"}])
    with (
        patch.object(server._client, "count_items", new=AsyncMock(side_effect=count_items)),
        patch.object(server._cone, "languages", new=cone_langs),
    ):
        genres = await server.publication_statistics(group_by="genre")
        langs = await server.publication_statistics(group_by="language")
    assert genres["buckets"] == [{"key": "ARTICLE", "count": 7}, {"key": "BOOK", "count": 3}]
    assert genres["totalMatchingRecords"] == 10
    assert langs["buckets"] == [{"key": "eng", "count": 9}, {"key": "deu", "count": 4}]
    cone_langs.assert_awaited_once()
    # the full JSON-model vocabularies are used, not a truncated subset
    assert "PREPRINT" in server._GENRES and "REVIEW_ARTICLE" in server._GENRES
    assert len(server._GENRES) == 49


async def test_publication_statistics_open_access_excludes_closed_locators():
    async def count_items(query):
        if isinstance(query, dict) and query.get("bool", {}).get("filter"):
            filt = query["bool"]["filter"][0]
            assert filt["bool"]["must"] == [{"term": {"files.visibility": "PUBLIC"}}]
            assert filt["bool"]["must_not"] == [{"term": {"files.oaStatus": "CLOSED_ACCESS"}}]
            return 40
        return 100

    with patch.object(server._client, "count_items", new=AsyncMock(side_effect=count_items)):
        out = await server.publication_statistics(group_by="open_access")
    assert out["totalMatchingRecords"] == 100
    assert out["buckets"] == [{"key": "open_access", "count": 40}, {"key": "closed", "count": 60}]


async def test_publication_statistics_oa_status_breakdown():
    async def count_items(query):
        val = query["bool"]["filter"][0]["term"]["files.oaStatus"]
        return {"GOLD": 5, "GREEN": 3, "CLOSED_ACCESS": 12}.get(val, 0)

    with patch.object(server._client, "count_items", new=AsyncMock(side_effect=count_items)):
        out = await server.publication_statistics(group_by="oa_status")
    assert out["buckets"][0] == {"key": "CLOSED_ACCESS", "count": 12}
    assert {"key": "GOLD", "count": 5} in out["buckets"]


async def test_publication_statistics_organization_fetches_records():
    recs = [_record_with_creators("MPI A"), _record_with_creators("MPI A", "MPI B")]
    with patch.object(server._client, "fetch_all", new=AsyncMock(return_value=recs)):
        out = await server.publication_statistics(group_by="organization")
    assert out["buckets"][0] == {"key": "MPI A", "count": 2}
    assert "aggregated from 2 fetched records" in out["note"]
