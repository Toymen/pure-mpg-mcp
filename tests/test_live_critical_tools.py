"""Opt-in live checks for the critical MCP tools.

Run with:
    uv run --extra dev pytest -m network

These tests intentionally touch the public PuRe/CONE services and a few public
scholarly enrichment APIs. They use low-volume requests and stable public IDs,
but they are still network tests: upstream outages should not block the normal
offline suite.
"""

import httpx
import pytest

from pure_mpg_mcp import server
from pure_mpg_mcp.client import PureClient
from pure_mpg_mcp.enrichment import unavailable_sources


pytestmark = [pytest.mark.network, pytest.mark.asyncio(loop_scope="module")]

LIVE_DOI = "10.1111/j.1467-7687.2008.00820.x"
LIVE_ITEM_ID = "item_1552993"
LIVE_FILE_ITEM_ID = "item_1554385"
LIVE_FILE_ID = "file_2123384"
LIVE_OU_ID = "ou_1497640"
LIVE_CONTEXT_ID = "ctx_1835112"


def _identifier_query() -> dict:
    return {
        "bool": {
            "should": [
                {"term": {"metadata.identifiers.id.keyword": LIVE_DOI}},
                {"match_phrase": {"metadata.identifiers.id": LIVE_DOI}},
            ],
            "minimum_should_match": 1,
        }
    }


def _assert_feed(text: str) -> None:
    assert text.lstrip().startswith("<?xml")
    assert "<feed" in text[:500]


async def test_live_publication_search_retrieval_export_and_files():
    search = await server.search_publications(identifier=LIVE_DOI, size=1)
    assert search["numberOfRecords"] >= 1
    assert search["items"][0]["itemId"] == LIVE_ITEM_ID

    raw = await server.search_raw(_identifier_query(), size=1)
    assert raw["items"][0]["itemId"] == LIVE_ITEM_ID

    by_doi = await server.find_by_doi(f"https://doi.org/{LIVE_DOI}")
    assert by_doi["items"][0]["itemId"] == LIVE_ITEM_ID

    item = await server.get_publication(LIVE_ITEM_ID)
    assert item["objectId"] == LIVE_ITEM_ID
    assert item["metadata"]["title"]

    item_export = await server.export_publication(LIVE_ITEM_ID)
    assert LIVE_DOI in item_export

    search_export = await server.export_search_results(query=_identifier_query(), size=1)
    assert LIVE_DOI in search_export

    file_meta = await server.get_file_metadata(LIVE_FILE_ITEM_ID, LIVE_FILE_ID)
    assert file_meta["contentUrl"].endswith(f"/items/{LIVE_FILE_ITEM_ID}/component/{LIVE_FILE_ID}/content")
    assert file_meta["thumbnailUrl"].endswith(f"/items/{LIVE_FILE_ITEM_ID}/component/{LIVE_FILE_ID}/thumbnail")
    assert any(key.startswith(("pdf:", "X-TIKA:")) for key in file_meta)


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

    _assert_feed(await server.recent_publications())
    _assert_feed(await server.open_access_feed())
    _assert_feed(await server.organization_feed(LIVE_OU_ID))

    info = await server.service_info()
    assert info["status"] == "ok"


async def test_live_authority_statistics_analysis_and_enrichment_tools():
    languages = await server.list_languages()
    codes = {entry["id"] for entry in languages["languages"]}
    assert {"eng", "deu"}.issubset(codes)

    authors = await server.resolve_author(name="Planck", limit=2)
    assert authors["candidates"]
    person = await server.resolve_author(person_id=authors["candidates"][0]["id"])
    assert person["personId"]

    author_publications = await server.author_publications(name="Planck", size=1)
    assert author_publications["numberOfRecords"] >= 1

    author_analysis = await server.analyze_authors(item_id=LIVE_ITEM_ID)
    assert author_analysis["summary"]["analyzedRecords"] == 1
    assert author_analysis["authors"]

    stats = await server.publication_statistics(query=_identifier_query(), group_by="open_access")
    assert {bucket["key"] for bucket in stats["buckets"]} == {"open_access", "closed"}
    assert stats["totalMatchingRecords"] >= 1

    metrics = await server.get_citation_metrics(doi=LIVE_DOI)
    if "error" in metrics:
        pytest.skip(f"enrichment sources unavailable for {LIVE_DOI}: {metrics['error']}")
    assert any(
        metrics.get(key) is not None
        for key in ("openalex_cited_by", "crossref_referenced_by", "semanticscholar_citations")
    )

    full_text = await server.find_full_text(item_id=LIVE_ITEM_ID)
    assert full_text["doi"] == LIVE_DOI
    if "unpaywall" in unavailable_sources(["unpaywall"]):
        assert full_text["notes"]["unpaywall"] == unavailable_sources(["unpaywall"])["unpaywall"]


@pytest.mark.limit
async def test_live_known_feed_search_limitation_is_explicit():
    """The live feed/search endpoint currently returns HTTP 500 for normal q values."""
    async with PureClient() as client:
        try:
            text = await client.feed_search("graphene")
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code >= 500
            assert "JsonParsingException" in exc.response.text
        else:
            _assert_feed(text)
