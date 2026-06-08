"""MCP server exposing the public read surface of the PuRe (PubMan) REST API.

PuRe is the Max Planck Society's publication repository (https://pure.mpg.de).
This server is anonymous and read-only: it can search and retrieve RELEASED,
publicly visible publication records, organizational units, collections, and
feeds. It cannot log in, write, or access embargoed/private content.

Run:
    pure-mpg-mcp           # stdio transport (default)
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import PureClient
from .models import summarize_search

mcp = FastMCP("pure-mpg")
_client = PureClient()


@mcp.tool()
async def search_publications(
    text: str | None = None,
    author: str | None = None,
    genre: str | None = None,
    year: int | None = None,
    size: int = 10,
    offset: int = 0,
    full_records: bool = False,
) -> dict[str, Any]:
    """Search Max Planck publications in PuRe.

    Builds an Elasticsearch query from simple filters. Use `text` for a
    free-text search across title/abstract/fulltext, `author` for a creator
    family name, `genre` for publication type (e.g. ARTICLE, BOOK, CONFERENCE_PAPER),
    and `year` for the publication year. Returns compact summaries by default;
    set `full_records=True` for raw PuRe records.

    Returns numberOfRecords plus a list of items (itemId, title, creators, doi, files).
    Fetch full metadata for a hit with `get_publication(itemId)`.
    """
    must: list[dict[str, Any]] = []
    if text:
        must.append({"simple_query_string": {"query": text}})
    if author:
        must.append(
            {"match": {"metadata.creators.person.familyName": author}}
        )
    if genre:
        must.append({"term": {"metadata.genre": genre}})
    if year:
        must.append(
            {
                "range": {
                    "metadata.datePublishedInPrint": {
                        "gte": f"{year}||/y",
                        "lte": f"{year}||/y",
                        "format": "yyyy",
                    }
                }
            }
        )
    query: dict[str, Any] = {"bool": {"must": must}} if must else {"match_all": {}}
    payload = await _client.search_items(query=query, size=size, from_=offset)
    return summarize_search(payload, include_raw=full_records)


@mcp.tool()
async def search_raw(
    query: dict[str, Any],
    size: int = 10,
    offset: int = 0,
    sort: list[dict[str, Any]] | None = None,
    full_records: bool = False,
) -> dict[str, Any]:
    """Run a raw Elasticsearch query against PuRe's /items/search.

    For advanced queries the simple `search_publications` filters can't express.
    `query` is an Elasticsearch query DSL object, e.g.
    {"bool": {"must": [{"match": {"metadata.title": "graphene"}}]}}.
    """
    payload = await _client.search_items(query=query, size=size, from_=offset, sort=sort)
    return summarize_search(payload, include_raw=full_records)


@mcp.tool()
async def get_publication(item_id: str) -> dict[str, Any]:
    """Get the full metadata record for one publication by its PuRe item id.

    `item_id` looks like "item_1552993" (as returned by search results).
    """
    return await _client.get_item(item_id)


@mcp.tool()
async def export_publication(
    item_id: str,
    format: str = "BibTex",
    citation: str | None = None,
    csl_cone_id: str | None = None,
) -> str:
    """Export a publication as a formatted citation or bibliographic record.

    `format` may be e.g. BibTex, ENDNOTE, MARC, ESCIDOC_SNIPPET. For formatted
    citations pass format="ESCIDOC_SNIPPET" with `citation` set to a style
    (e.g. "APA") and optionally `csl_cone_id` for a CSL style. Returns the raw
    text/markup of the export.
    """
    return await _client.export_item(item_id, format=format, citation=citation, csl_cone_id=csl_cone_id)


@mcp.tool()
async def get_file_metadata(item_id: str, component_id: str) -> dict[str, Any]:
    """Get metadata for a file (component) attached to a publication.

    `component_id` comes from the `files[].componentId` of a publication.
    The downloadable content lives at
    {base}/items/{item_id}/component/{component_id}/content when visibility is PUBLIC.
    """
    return await _client.get_component_metadata(item_id, component_id)


@mcp.tool()
async def search_organizations(name: str | None = None, size: int = 10, offset: int = 0) -> dict[str, Any]:
    """Search Max Planck organizational units (institutes, departments).

    Pass `name` to match on the unit name, or omit for a broad listing.
    Returns raw OU records (objectId, name, parent affiliations).
    """
    query: dict[str, Any] = (
        {"match": {"metadata.name": name}} if name else {"match_all": {}}
    )
    return await _client.search_ous(query=query, size=size, from_=offset)


@mcp.tool()
async def list_top_organizations() -> dict[str, Any]:
    """List the top-level (root) Max Planck organizational units."""
    return await _client.ous_toplevel()


@mcp.tool()
async def search_collections(name: str | None = None, size: int = 10, offset: int = 0) -> dict[str, Any]:
    """Search PuRe contexts (collections that group publications)."""
    query: dict[str, Any] = (
        {"match": {"name": name}} if name else {"match_all": {}}
    )
    return await _client.search_contexts(query=query, size=size, from_=offset)


@mcp.tool()
async def recent_publications() -> str:
    """Get the feed of recently released publications (RSS/Atom XML)."""
    return await _client.feed_recent()


@mcp.tool()
async def open_access_feed() -> str:
    """Get the feed of recent open-access publications (RSS/Atom XML)."""
    return await _client.feed_open_access()


@mcp.tool()
async def service_info() -> dict[str, Any]:
    """Get version and status information for the PuRe instance."""
    return await _client.service_info()


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
