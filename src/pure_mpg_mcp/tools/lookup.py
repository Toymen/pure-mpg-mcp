"""Lookup & authority tools (CONE persons/languages, DOI/author search)."""

from __future__ import annotations

from typing import Any

from ..context import _client, _cone, mcp
from ..models import summarize_search
from ..vocab import _DATE_PUBLISHED


@mcp.tool()
async def find_by_doi(doi: str) -> dict[str, Any]:
    """Find a Max Planck publication by its DOI.

    Accepts a bare DOI ("10.1021/acsaelm.5c02138") or a doi.org URL. Returns
    matching item summaries (usually one).
    """
    payload = await _client.find_by_doi(doi)
    return summarize_search(payload)


@mcp.tool()
async def resolve_author(name: str | None = None, person_id: str | None = None, limit: int = 10) -> dict[str, Any]:
    """Resolve an author against the CONE authority service.

    Pass `name` to search (returns candidate persons with their CONE ids), or a
    `person_id` (e.g. "persons314810") to get the canonical record: full given
    name, family name, affiliation, and ORCID when known. Useful for
    disambiguation and for expanding initials to full first names.
    """
    if person_id:
        return await _cone.resolve_person(person_id)
    if name:
        candidates = await _cone.query_persons(name, limit=limit)
        return {"query": name, "candidates": candidates}
    return {"error": "provide either name or person_id"}


@mcp.tool()
async def list_languages() -> dict[str, Any]:
    """List every ISO 639-3 language code PubMan accepts, from the CONE authority.

    Each entry has `id` (the code to pass as `search_publications(language=...)`
    or `publication_statistics` groups by) and `value` (its display name). This
    is the authoritative source `publication_statistics(group_by="language")`
    itself queries against.
    """
    return {"languages": await _cone.languages()}


@mcp.tool()
async def author_publications(
    name: str | None = None,
    person_id: str | None = None,
    size: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List publications by a given author.

    Provide a CONE `person_id` for a precise match (queried against the
    creator's authority id), or a `name` (family name) for a looser match.
    """
    if person_id:
        pid = person_id.rstrip("/").split("/")[-1]
        query: dict[str, Any] = {
            "match": {"metadata.creators.person.identifier.id": f"/persons/resource/{pid}"}
        }
    elif name:
        query = {"match": {"metadata.creators.person.familyName": name}}
    else:
        return {"error": "provide either name or person_id"}
    payload = await _client.search_items(
        query=query, size=size, from_=offset,
        sort=[{f: {"order": "desc", "missing": "_last"}} for f in _DATE_PUBLISHED],
    )
    return summarize_search(payload)
