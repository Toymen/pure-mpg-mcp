"""Free full-text location tool."""

from __future__ import annotations

from typing import Any

from ..context import _enrich, mcp
from ..enrichment import unavailable_sources
from .enrichment import _doi_for


@mcp.tool()
async def find_full_text(item_id: str | None = None, doi: str | None = None) -> dict[str, Any]:
    """Locate free full text for a PuRe publication.

    Checks PuRe's own attached files first (the canonical source), then falls
    back to public open-access locations via Unpaywall and OpenAlex. Provide a
    PuRe `item_id` (preferred) or a `doi`.
    """
    resolved_doi, record = await _doi_for(item_id, doi)
    pure_files = []
    if record:
        for comp in record.get("files", []) or []:
            fmd = comp.get("metadata", {}) or {}
            visibility = comp.get("visibility") or fmd.get("visibility")
            if (visibility or "").upper() == "PUBLIC":
                pure_files.append(
                    {
                        "componentId": comp.get("objectId"),
                        "name": fmd.get("title") or fmd.get("name"),
                        "license": fmd.get("license"),
                    }
                )
    result: dict[str, Any] = {"doi": resolved_doi, "purePublicFiles": pure_files}
    if resolved_doi:
        ext = await _enrich.fetch(resolved_doi, ["unpaywall", "openalex"])
        up = ext.get("unpaywall") or {}
        result["isOpenAccess"] = up.get("is_oa") or (pure_files != [])
        result["oaStatus"] = up.get("oa_status")
        result["bestFreePdf"] = up.get("best_oa_pdf")
        result["bestFreeUrl"] = up.get("best_oa_url")
        skipped = unavailable_sources(["unpaywall"])
        if skipped:
            result["notes"] = skipped
    else:
        result["isOpenAccess"] = pure_files != []
    return result
