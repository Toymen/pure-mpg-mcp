"""External-enrichment tools: attach public scholarly signals to a PuRe record.

PuRe is the spine; external public sources hang off the identifiers PuRe
provides (DOI). All sources are free and require no auth.
"""

from __future__ import annotations

from typing import Any

from ..context import _client, _enrich, mcp
from ..enrichment import SOURCES, unavailable_sources
from ..models import _first_identifier, summarize_item


async def _doi_for(item_id: str | None, doi: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve a DOI plus the canonical PuRe item, keeping PuRe as the spine.

    With `item_id`, the PuRe record is fetched and its DOI extracted (PuRe is
    authoritative). `doi` is accepted only as a convenience shortcut.
    """
    if item_id:
        record = await _client.get_item(item_id)
        md = record.get("metadata", {}) or {}
        return _first_identifier(md, "DOI") or doi, record
    return doi, None


@mcp.tool()
async def enrich_publication(
    item_id: str | None = None,
    doi: str | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Enrich a PuRe publication with external public scholarly data.

    PuRe is the canonical record; this attaches signals from external sources
    keyed on the publication's DOI. Provide a PuRe `item_id` (preferred — its
    DOI is read from the authoritative record) or a `doi` directly.

    `sources` selects among: "openalex" (citations, topics, institutions/ROR,
    OA), "crossref" (references, funders, license), "unpaywall" (OA status +
    free full-text PDF), "semanticscholar" (influential citations, TLDR
    summary). Defaults to openalex + crossref + unpaywall. Sources that have no
    record for the DOI are omitted.

    Returns the PuRe item summary plus an `enrichment` block per source.
    """
    chosen = sources or ["openalex", "crossref", "unpaywall"]
    invalid = [s for s in chosen if s not in SOURCES]
    if invalid:
        return {"error": f"unknown source(s): {invalid}", "available": list(SOURCES)}
    resolved_doi, record = await _doi_for(item_id, doi)
    if not resolved_doi:
        return {"error": "no DOI available for this publication", "itemId": item_id}
    enrichment = await _enrich.fetch(resolved_doi, chosen)
    result = {
        "pure": summarize_item(record) if record else None,
        "doi": resolved_doi,
        "enrichment": enrichment,
        "sourcesQueried": chosen,
        "sourcesReturned": list(enrichment.keys()),
    }
    skipped = unavailable_sources(chosen)
    if skipped:
        result["sourcesSkipped"] = skipped
    return result


@mcp.tool()
async def get_citation_metrics(item_id: str | None = None, doi: str | None = None) -> dict[str, Any]:
    """Compare citation counts for a PuRe publication across public sources.

    Resolves the DOI from the PuRe item (or accepts a `doi` directly) and
    reports citation counts side by side from OpenAlex, Crossref, and Semantic
    Scholar (including Semantic Scholar's influential-citation count). Counts
    differ by source because each indexes a different corpus.
    """
    resolved_doi, _ = await _doi_for(item_id, doi)
    if not resolved_doi:
        return {"error": "no DOI available for this publication", "itemId": item_id}
    data = await _enrich.fetch(resolved_doi, ["openalex", "crossref", "semanticscholar"])
    return {
        "doi": resolved_doi,
        "openalex_cited_by": (data.get("openalex") or {}).get("cited_by_count"),
        "crossref_referenced_by": (data.get("crossref") or {}).get("is_referenced_by_count"),
        "semanticscholar_citations": (data.get("semanticscholar") or {}).get("citation_count"),
        "semanticscholar_influential": (data.get("semanticscholar") or {}).get("influential_citation_count"),
    }
