"""Offline tests for the search_publications/search_raw/get_publication tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pure_mpg_mcp import server

from helpers import _search_payload


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
    with pytest.raises(ValueError, match="unknown date_field"):
        await server.search_publications(date_from="2020", date_field="bogus")


async def test_search_raw_passes_query_through():
    mock = AsyncMock(return_value=_search_payload("item_2"))
    q = {"bool": {"must": [{"match": {"metadata.title": "x"}}]}}
    with patch.object(server._client, "search_items", new=mock):
        out = await server.search_raw(query=q, size=3, sort=[{"f": {"order": "asc"}}])
    assert mock.call_args.kwargs["query"] == q
    assert out["items"][0]["itemId"] == "item_2"
