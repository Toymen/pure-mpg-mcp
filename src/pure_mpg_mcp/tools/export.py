"""Export and file-metadata tools."""

from __future__ import annotations

from typing import Any

from ..context import _client, mcp


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
async def export_search_results(
    query: dict[str, Any] | None = None,
    format: str = "BibTex",
    citation: str | None = None,
    csl_cone_id: str | None = None,
    size: int = 100,
    offset: int = 0,
    sort: list[dict[str, Any]] | None = None,
) -> str:
    """Export a whole set of search results in one call (bulk citation export).

    Avoids calling `export_publication` once per hit. `query` is an
    Elasticsearch query DSL object (default: all records). `format` may be
    e.g. BibTex, ENDNOTE, MARC_XML, JSON_CITATION, ESCIDOC_SNIPPET, PDF, DOCX.
    For formatted citations pass a citation-expecting format with `citation`
    set to a style (e.g. "APA") and optionally `csl_cone_id`. The PuRe API
    caps a single export at 5000 records — page with `size`/`offset` beyond
    that. Returns the raw exported text.
    """
    q = query or {"match_all": {}}
    return await _client.export_search(
        query=q, format=format, citation=citation, csl_cone_id=csl_cone_id,
        size=size, from_=offset, sort=sort,
    )


@mcp.tool()
async def get_file_metadata(item_id: str, component_id: str) -> dict[str, Any]:
    """Get metadata for a file (component) attached to a publication, plus its URLs.

    `component_id` comes from the `files[].componentId` of a publication.
    `contentUrl`/`thumbnailUrl` are reachable anonymously when the file's
    visibility is PUBLIC.
    """
    meta = await _client.get_component_metadata(item_id, component_id)
    meta["contentUrl"] = _client.component_content_url(item_id, component_id)
    meta["thumbnailUrl"] = _client.component_thumbnail_url(item_id, component_id)
    return meta
