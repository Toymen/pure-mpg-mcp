"""Research-data discovery tools: DOI/ORCID -> linked datasets."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..context import _datasets, mcp
from ..datasets import DOI_SOURCES, ORCID_SOURCES, normalize_orcid
from ..datasets.common import strip_doi_url
from ..models import summarize_item
from .enrichment import _doi_for


def _google_dataset_search_url(query: str) -> str:
    return f"https://datasetsearch.research.google.com/search?query={quote(query)}"


def _merge_dataset_hits(by_source: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for source, hits in by_source.items():
        for raw in hits:
            doi = strip_doi_url(raw.get("doi"))
            title = raw.get("title")
            key = f"doi:{doi.lower()}" if doi else f"title:{(title or '').strip().lower()}"
            if not key.endswith(":"):
                existing = index.get(key)
            else:
                existing = None
            if existing is None:
                hit = {
                    "doi": doi,
                    "title": title,
                    "publisher": raw.get("publisher"),
                    "year": raw.get("year"),
                    "relation": raw.get("relation"),
                    "sources": [source],
                }
                merged.append(hit)
                if not key.endswith(":"):
                    index[key] = hit
                continue
            existing["sources"].append(source)
            for field in ("title", "publisher", "year", "relation"):
                if existing.get(field) is None and raw.get(field) is not None:
                    existing[field] = raw[field]
    return merged


@mcp.tool()
async def find_research_data(
    item_id: str | None = None,
    doi: str | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Find datasets linked to a PuRe publication DOI.

    Provide a PuRe `item_id` (preferred — the DOI is read from the authoritative
    PuRe record) or pass a `doi` directly. The tool fans out to public,
    unauthenticated research-data services: ScholeXplorer, DataCite, B2FIND,
    Crossref relation metadata, Zenodo, Figshare, and Dryad. Results are
    normalized and deduplicated by dataset DOI/title, while `bySource` preserves
    the original provider evidence.
    """
    chosen = sources or list(DOI_SOURCES)
    invalid = [s for s in chosen if s not in DOI_SOURCES]
    if invalid:
        return {"error": f"unknown source(s): {invalid}", "available": list(DOI_SOURCES)}
    resolved_doi, record = await _doi_for(item_id, doi)
    if not resolved_doi:
        return {"error": "no DOI available for this publication", "itemId": item_id}
    by_source = await _datasets.by_doi(resolved_doi, chosen)
    datasets = _merge_dataset_hits(by_source)
    return {
        "pure": summarize_item(record) if record else None,
        "doi": resolved_doi,
        "hasResearchData": bool(datasets),
        "datasets": datasets,
        "bySource": by_source,
        "sourcesQueried": chosen,
        "sourcesReturned": list(by_source.keys()),
        "googleDatasetSearchUrl": _google_dataset_search_url(resolved_doi),
    }


@mcp.tool()
async def find_research_data_by_orcid(
    orcid: str,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Find datasets authored by a researcher ORCID.

    Accepts a bare ORCID or an orcid.org URL. The tool queries DataCite,
    OpenAIRE Graph, OpenAlex, Zenodo, and Figshare, then normalizes and
    deduplicates dataset hits. Use this when the publication DOI is absent or
    when the question is author-centric rather than publication-centric.
    """
    normalized = normalize_orcid(orcid)
    if normalized is None:
        return {"error": "invalid ORCID", "orcid": orcid}
    chosen = sources or list(ORCID_SOURCES)
    invalid = [s for s in chosen if s not in ORCID_SOURCES]
    if invalid:
        return {"error": f"unknown source(s): {invalid}", "available": list(ORCID_SOURCES)}
    by_source = await _datasets.by_orcid(normalized, chosen)
    datasets = _merge_dataset_hits(by_source)
    return {
        "orcid": normalized,
        "hasResearchData": bool(datasets),
        "datasets": datasets,
        "bySource": by_source,
        "sourcesQueried": chosen,
        "sourcesReturned": list(by_source.keys()),
        "googleDatasetSearchUrl": _google_dataset_search_url(normalized),
    }
