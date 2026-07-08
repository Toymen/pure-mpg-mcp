"""Collection (context), feed, and service-info tools."""

from __future__ import annotations

from typing import Any

from ..context import _client, mcp


@mcp.tool()
async def search_collections(name: str | None = None, size: int = 10, offset: int = 0) -> dict[str, Any]:
    """Search PuRe contexts (collections that group publications)."""
    query: dict[str, Any] = (
        {"match": {"name": name}} if name else {"match_all": {}}
    )
    return await _client.search_contexts(query=query, size=size, from_=offset)


@mcp.tool()
async def get_collection(context_id: str) -> dict[str, Any]:
    """Get one PuRe context (collection) by id (e.g. "ctx_123456")."""
    return await _client.get_context(context_id)


@mcp.tool()
async def recent_publications() -> str:
    """Get the feed of recently released publications (RSS/Atom XML)."""
    return await _client.feed_recent()


@mcp.tool()
async def open_access_feed() -> str:
    """Get the feed of recent open-access publications (RSS/Atom XML)."""
    return await _client.feed_open_access()


@mcp.tool()
async def organization_feed(ou_id: str) -> str:
    """Get the feed of recent releases for one organizational unit (RSS/Atom XML)."""
    return await _client.feed_organization(ou_id)


@mcp.tool()
async def search_feed(query_text: str) -> str:
    """Run a free-text search and get the results as an RSS/Atom feed.

    `query_text` is the PuRe search-box query string (same syntax as the
    PubMan UI search box), not an Elasticsearch DSL object.
    """
    return await _client.feed_search(query_text)


@mcp.tool()
async def service_info() -> dict[str, Any]:
    """Get version and status information for the PuRe instance."""
    return await _client.service_info()
