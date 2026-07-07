"""Offline tests for the MCP tool layer in server.py.

The FastMCP ``@mcp.tool()`` decorator returns the plain function, so tools are
called directly with the module-level clients (`_client`, `_cone`, `_enrich`)
mocked out — no network involved.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from pure_mpg_mcp import server


def _search_payload(*item_ids: str, total: int | None = None) -> dict:
    return {
        "numberOfRecords": total if total is not None else len(item_ids),
        "records": [{"data": {"objectId": iid, "metadata": {"title": iid}}} for iid in item_ids],
    }


async def test_search_publications_builds_filtered_query():
    mock = AsyncMock(return_value=_search_payload("item_1"))
    with patch.object(server._client, "search_items", new=mock):
        out = await server.search_publications(text="graphene", author="Planck", genre="ARTICLE", year=2020)
    assert out["numberOfRecords"] == 1
    query = mock.call_args.kwargs["query"]
    must = query["bool"]["must"]
    assert {"simple_query_string": {"query": "graphene"}} in must
    assert {"match": {"metadata.creators.person.familyName": "Planck"}} in must
    assert {"term": {"metadata.genre": "ARTICLE"}} in must
    assert any("range" in clause for clause in must)


async def test_search_publications_defaults_to_match_all():
    mock = AsyncMock(return_value=_search_payload())
    with patch.object(server._client, "search_items", new=mock):
        await server.search_publications()
    assert mock.call_args.kwargs["query"] == {"match_all": {}}


async def test_search_raw_passes_query_through():
    mock = AsyncMock(return_value=_search_payload("item_2"))
    q = {"bool": {"must": [{"match": {"metadata.title": "x"}}]}}
    with patch.object(server._client, "search_items", new=mock):
        out = await server.search_raw(query=q, size=3, sort=[{"f": {"order": "asc"}}])
    assert mock.call_args.kwargs["query"] == q
    assert out["items"][0]["itemId"] == "item_2"


async def test_get_publication_and_export_and_file_metadata():
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value={"objectId": "item_3"})),
        patch.object(server._client, "export_item", new=AsyncMock(return_value="@article{...}")),
        patch.object(server._client, "get_component_metadata", new=AsyncMock(return_value={"f": 1})),
    ):
        assert (await server.get_publication("item_3"))["objectId"] == "item_3"
        assert (await server.export_publication("item_3")).startswith("@article")
        assert await server.get_file_metadata("item_3", "comp_1") == {"f": 1}


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


def _dated_record(date: str) -> dict:
    return {"numberOfRecords": 1, "records": [{"data": {"metadata": {"datePublishedInPrint": date}}}]}


async def test_publication_statistics_year_counts_each_year():
    counts = {"2019": 2, "2020": 0, "2021": 5}

    async def count_items(query):
        rng = query["bool"]["filter"][0]["range"]["metadata.datePublishedInPrint"]
        return counts[rng["gte"][:4]]

    search = AsyncMock(side_effect=[_dated_record("2019-03-01"), _dated_record("2021-11-30")])
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
        patch.object(server._client, "search_items", new=AsyncMock(side_effect=[empty, empty])),
        patch.object(server._client, "count_items", new=AsyncMock(return_value=0)),
    ):
        out = await server.publication_statistics(group_by="year")
    assert out["buckets"] == []


async def test_publication_statistics_genre_and_language():
    async def count_items(query):
        clause = query["bool"]["filter"][0]["term"]
        val = next(iter(clause.values()))
        return {"ARTICLE": 7, "BOOK": 3, "eng": 9, "deu": 4}.get(val, 0)

    with patch.object(server._client, "count_items", new=AsyncMock(side_effect=count_items)):
        genres = await server.publication_statistics(group_by="genre")
        langs = await server.publication_statistics(group_by="language")
    assert genres["buckets"] == [{"key": "ARTICLE", "count": 7}, {"key": "BOOK", "count": 3}]
    assert genres["totalMatchingRecords"] == 10
    assert langs["buckets"] == [{"key": "eng", "count": 9}, {"key": "deu", "count": 4}]


async def test_publication_statistics_open_access():
    async def count_items(query):
        # the OA sub-query wraps the base in bool/filter; the total does not
        return 40 if "bool" in query and query["bool"].get("filter") else 100

    with patch.object(server._client, "count_items", new=AsyncMock(side_effect=count_items)):
        out = await server.publication_statistics(group_by="open_access")
    assert out["totalMatchingRecords"] == 100
    assert out["buckets"] == [{"key": "open_access", "count": 40}, {"key": "closed", "count": 60}]


def _record_with_creators(*orgs: str) -> dict:
    return {
        "data": {
            "objectId": "item_x",
            "metadata": {
                "creators": [
                    {
                        "role": "AUTHOR",
                        "person": {"familyName": "Planck", "organizations": [{"name": o} for o in orgs]},
                    }
                ]
            },
        }
    }


async def test_publication_statistics_organization_fetches_records():
    recs = [_record_with_creators("MPI A"), _record_with_creators("MPI A", "MPI B")]
    with patch.object(server._client, "fetch_all", new=AsyncMock(return_value=recs)):
        out = await server.publication_statistics(group_by="organization")
    assert out["buckets"][0] == {"key": "MPI A", "count": 2}
    assert "aggregated from 2 fetched records" in out["note"]


async def test_coauthorship_analysis():
    recs = [_record_with_creators("MPI A")]
    with patch.object(server._client, "fetch_all", new=AsyncMock(return_value=recs)):
        out = await server.coauthorship_analysis()
    assert out["analyzedRecords"] == 1
    assert out["soloAuthored"] == 1


def _authored_record(given: str | None, cone_id: str | None = None) -> dict:
    person: dict = {"familyName": "Planck", "givenName": given}
    if cone_id:
        person["identifier"] = {"id": cone_id}
    return {"data": {"objectId": "item_a", "metadata": {"creators": [{"person": person}]}}}


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


def _item_with_doi(doi: str | None) -> dict:
    identifiers = [{"type": "DOI", "id": doi}] if doi else []
    return {
        "objectId": "item_d",
        "metadata": {"title": "T", "identifiers": identifiers},
        "files": [
            {"objectId": "comp_1", "metadata": {"visibility": "PUBLIC", "title": "paper.pdf"}},
            {"objectId": "comp_2", "metadata": {"visibility": "PRIVATE"}},
        ],
    }


async def test_enrich_publication_rejects_unknown_source():
    out = await server.enrich_publication(doi="10.1/x", sources=["openalex", "nope"])
    assert "unknown source(s)" in out["error"]


async def test_enrich_publication_requires_doi():
    with patch.object(server._client, "get_item", new=AsyncMock(return_value=_item_with_doi(None))):
        out = await server.enrich_publication(item_id="item_d")
    assert out["error"] == "no DOI available for this publication"


async def test_enrich_publication_success_from_item():
    enrichment = {"openalex": {"cited_by_count": 12}}
    with (
        patch.object(server._client, "get_item", new=AsyncMock(return_value=_item_with_doi("10.1/x"))),
        patch.object(server._enrich, "fetch", new=AsyncMock(return_value=enrichment)) as fetch,
    ):
        out = await server.enrich_publication(item_id="item_d", sources=["openalex"])
    assert out["doi"] == "10.1/x"
    assert out["sourcesReturned"] == ["openalex"]
    assert out["pure"]["itemId"] == "item_d"
    fetch.assert_awaited_once_with("10.1/x", ["openalex"])


async def test_get_citation_metrics():
    data = {
        "openalex": {"cited_by_count": 10},
        "crossref": {"is_referenced_by_count": 8},
        "semanticscholar": {"citation_count": 9, "influential_citation_count": 2},
    }
    with patch.object(server._enrich, "fetch", new=AsyncMock(return_value=data)):
        out = await server.get_citation_metrics(doi="10.1/x")
    assert out["openalex_cited_by"] == 10
    assert out["crossref_referenced_by"] == 8
    assert out["semanticscholar_influential"] == 2
    assert "error" in await server.get_citation_metrics()


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


async def test_find_full_text_without_doi():
    out = await server.find_full_text()
    assert out == {"doi": None, "purePublicFiles": [], "isOpenAccess": False}


def test_transport_security_disabled_without_hosts(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    settings = server._transport_security()
    assert settings.enable_dns_rebinding_protection is False


def test_transport_security_allows_configured_hosts(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.org")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "app.onrender.com")
    settings = server._transport_security()
    assert "mcp.example.org" in settings.allowed_hosts
    assert "app.onrender.com:*" in settings.allowed_hosts
    assert "https://mcp.example.org" in settings.allowed_origins


def test_main_selects_transport(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(server.mcp, "run", run)
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    server.main()
    run.assert_called_once_with(transport="streamable-http")
    assert server.mcp.settings.port == 9999

    run.reset_mock()
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    server.main()
    run.assert_called_once_with()
