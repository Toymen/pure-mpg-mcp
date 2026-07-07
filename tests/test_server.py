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
    assert {
        "multi_match": {
            "query": "Planck",
            "fields": ["metadata.creators.person.familyName", "metadata.creators.person.givenName"],
        }
    } in must
    assert {"term": {"metadata.genre": "ARTICLE"}} in must
    assert any("bool" in clause and "should" in clause.get("bool", {}) for clause in must)


async def test_search_publications_defaults_to_match_all():
    mock = AsyncMock(return_value=_search_payload())
    with patch.object(server._client, "search_items", new=mock):
        await server.search_publications()
    assert mock.call_args.kwargs["query"] == {"match_all": {}}


async def test_search_publications_covers_every_advanced_search_field():
    mock = AsyncMock(return_value=_search_payload("item_1"))
    with patch.object(server._client, "search_items", new=mock):
        await server.search_publications(
            title="Eigenvalue Outliers",
            keyword="Stochastic processes",  # Schlagwörter
            classification="Physics",  # Klassifikation
            fulltext="graphene",  # Volltext
            orcid="https://orcid.org/0000-0001-5849-8751",
            organization="ou_2117288",
            review_method="PEER",
            language="eng",
            source="Physical Review Letters",
            identifier="10.1103/PhysRevLett.117.224101",
            local_tag="Department1",
            collection="ctx_28054",
            project="Horizon Europe",
            event="ICML",
            date_from="2020", date_to="2021", date_field="published_online",
        )
    must = mock.call_args.kwargs["query"]["bool"]["must"]
    assert {"match": {"metadata.title": "Eigenvalue Outliers"}} in must
    assert {"match": {"metadata.freeKeywords": "Stochastic processes"}} in must
    assert {"match": {"metadata.subjects.value": "Physics"}} in must
    assert {"match": {"metadata.creators.person.orcid": "0000-0001-5849-8751"}} in must
    assert {"term": {"metadata.reviewMethod": "PEER"}} in must
    assert {"term": {"metadata.languages": "eng"}} in must
    assert {"match": {"metadata.sources.title": "Physical Review Letters"}} in must
    assert {"match": {"localTags": "Department1"}} in must
    assert {"term": {"context.objectId": "ctx_28054"}} in must
    assert {"match": {"metadata.event.title": "ICML"}} in must
    assert {"range": {"metadata.datePublishedOnline": {"gte": "2020||/y", "lte": "2021||/y", "format": "yyyy"}}} in must

    org_clause = next(c for c in must if "bool" in c and "should" in c["bool"] and c["bool"]["should"][0] == {
        "term": {"metadata.creators.person.organizations.identifier": "ou_2117288"}
    })
    assert org_clause is not None

    fulltext_clause = next(c for c in must if "simple_query_string" in c and c["simple_query_string"]["query"] == "graphene")
    assert "fulltext" in fulltext_clause["simple_query_string"]["fields"]

    identifier_clause = next(c for c in must if "bool" in c and any(
        s.get("term", {}).get("metadata.identifiers.id.keyword") == "10.1103/PhysRevLett.117.224101"
        for s in c["bool"]["should"]
    ))
    assert identifier_clause is not None

    project_clause = next(c for c in must if "bool" in c and any(
        "projectInfo" in str(s) for s in c["bool"]["should"]
    ))
    assert project_clause is not None


async def test_search_publications_organization_name_falls_back_to_match():
    mock = AsyncMock(return_value=_search_payload())
    with patch.object(server._client, "search_items", new=mock):
        await server.search_publications(organization="Max Planck Institute for the Physics of Complex Systems")
    must = mock.call_args.kwargs["query"]["bool"]["must"]
    assert {
        "match": {
            "metadata.creators.person.organizations.name": "Max Planck Institute for the Physics of Complex Systems"
        }
    } in must


async def test_search_publications_rejects_unknown_date_field():
    import pytest

    with pytest.raises(ValueError, match="unknown date_field"):
        await server.search_publications(date_from="2020", date_field="bogus")


async def test_search_raw_passes_query_through():
    mock = AsyncMock(return_value=_search_payload("item_2"))
    q = {"bool": {"must": [{"match": {"metadata.title": "x"}}]}}
    with patch.object(server._client, "search_items", new=mock):
        out = await server.search_raw(query=q, size=3, sort=[{"f": {"order": "asc"}}])
    assert mock.call_args.kwargs["query"] == q
    assert out["items"][0]["itemId"] == "item_2"


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


def _dated_record(field: str, date: str) -> dict:
    return {"numberOfRecords": 1, "records": [{"data": {"metadata": {field: date}}}]}


def _year_of_filter(query: dict) -> str:
    """Extract the queried year from a _date_clause filter (bool/should of ranges)."""
    filt = query["bool"]["filter"][0]
    clause = filt["bool"]["should"][0] if "bool" in filt else filt
    return next(iter(clause["range"].values()))["gte"][:4]


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
