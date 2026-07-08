"""Author-centric analysis tools: co-authorship patterns and per-author enrichment."""

from __future__ import annotations

from typing import Any

from .. import analysis
from ..context import _client, _cone, mcp


@mcp.tool()
async def coauthorship_analysis(
    query: dict[str, Any] | None = None,
    max_records: int | None = None,
    top: int = 25,
) -> dict[str, Any]:
    """Analyze collaboration patterns across a set of publications.

    Returns average team size, count of solo-authored works, and the top
    collaborating authors and institutions, counting every creator role
    (AUTHOR, EDITOR, TRANSLATOR, DIRECTOR, ...) — not just authors. `query` is
    an Elasticsearch query DSL object (default: all records). Set
    `max_records` to an integer to limit the sample; the default (null)
    fetches all matching records.
    """
    q = query or {"match_all": {}}
    records = await _client.fetch_all(q, max_records=max_records)
    return analysis.coauthorship(records, top=top)


@mcp.tool()
async def analyze_authors(
    item_id: str | None = None,
    query: dict[str, Any] | None = None,
    enrich: bool = True,
    max_records: int | None = None,
) -> dict[str, Any]:
    """Extract and enrich the authors of a publication or a set of publications.

    A general author-analysis tool. Provide `item_id` for one publication, or
    `query` (Elasticsearch DSL) for an aggregate over publications. Set
    `max_records` to an integer to limit the sample; the default (null) fetches
    all matching records. Returns every creator regardless of role (AUTHOR,
    EDITOR, TRANSLATOR, DIRECTOR, REFEREE, INVENTOR, ...) or type — PubMan
    allows a creator to be a PERSON or an ORGANIZATION (a corporate/
    institutional author); the latter appear with their name in `familyName`
    and `type="ORGANIZATION"` rather than being dropped. Each entry also
    carries `role` plus `personId`/`orcid` so grouping, filtering, or dedup by
    identity is left to the caller instead of being decided here. Also
    returns a summary (distinct authors, distinct institutions, ORCID
    coverage).

    When `enrich` is true (default), authors whose given name is only an initial
    are resolved against the CONE authority service to fill in the full given
    name (expanding "J." to "Jan"), ORCID, and canonical affiliation when
    available.
    """
    if item_id:
        records = [await _client.get_item(item_id)]
    else:
        records = await _client.fetch_all(query or {"match_all": {}}, max_records=max_records)

    per_author: list[dict[str, Any]] = []
    institutions: set[str] = set()
    for rec in records:
        rid = analysis._data(rec).get("objectId")
        for person in analysis.creators(rec):
            cone_id = (person.get("identifier") or {}).get("id")
            entry: dict[str, Any] = {
                "itemId": rid,
                "role": person.get("role"),
                "type": person.get("type"),
                "familyName": person.get("familyName"),
                "firstName": analysis.clean_given_name(person.get("givenName")),
                "personId": cone_id.rstrip("/").split("/")[-1] if cone_id else None,
                "orcid": person.get("orcid"),
                "affiliation": None,
            }
            for org in person.get("organizations", []) or []:
                if org.get("name"):
                    institutions.add(org["name"])
                    entry["affiliation"] = entry["affiliation"] or org["name"]
            if enrich and cone_id and entry["firstName"] is None:
                try:
                    resolved = await _cone.resolve_person(cone_id)
                    entry["firstName"] = analysis.clean_given_name(resolved.get("givenName"))
                    entry["orcid"] = entry["orcid"] or resolved.get("orcid")
                    entry["affiliation"] = entry["affiliation"] or resolved.get("affiliation")
                except Exception:  # noqa: BLE001 — authority lookups are best-effort
                    pass
            per_author.append(entry)

    summary: dict[str, Any] = {
        "analyzedRecords": len(records),
        "authorMentions": len(per_author),
        "distinctAuthors": len({(a["familyName"], a["firstName"]) for a in per_author}),
        "distinctInstitutions": len(institutions),
        "withOrcid": sum(1 for a in per_author if a.get("orcid")),
    }
    return {"summary": summary, "authors": per_author}
