"""MCP server exposing the public read surface of the PuRe (PubMan) REST API.

PuRe is the Max Planck Society's publication repository (https://pure.mpg.de).
This server is anonymous and read-only: it can search and retrieve RELEASED,
publicly visible publication records, organizational units, collections, and
feeds. It cannot log in, write, or access embargoed/private content.

Run:
    pure-mpg-mcp                       # stdio transport (default; local clients)
    MCP_TRANSPORT=http pure-mpg-mcp    # streamable-HTTP at http://0.0.0.0:$PORT/mcp
                                       # (for hosting a remote connector URL)
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from mcp.server.transport_security import TransportSecuritySettings

from . import analysis
from .client import PureClient
from .cone import ConeClient
from .enrichment import SOURCES, Enrichment, unavailable_sources
from .models import _first_identifier, summarize_item, summarize_search

mcp = FastMCP("pure-mpg")
_client = PureClient()
_cone = ConeClient()
_enrich = Enrichment()

# --- publication_statistics: count-based aggregation helpers ---------------

_STATS_CONCURRENCY = 8  # max parallel count requests

_GENRES = [
    "ARTICLE", "BOOK", "BOOK_ITEM", "CONFERENCE_PAPER", "DATA_PUBLICATION",
    "DATASET", "FILM", "MANUAL", "MONOGRAPH", "OTHER", "PAPER", "PATENT",
    "POSTER", "PROCEEDINGS", "REPORT", "SOFTWARE", "TALK_AT_EVENT", "THESIS",
    "COURSEWARE_LECTURE",
]

_LANGUAGES = [
    "ara", "cat", "ces", "dan", "deu", "ell", "eng", "fin", "fra", "heb",
    "hun", "ita", "jpn", "kor", "lat", "nld", "nor", "pol", "por", "rus",
    "spa", "swe", "tur", "vie", "zho",
]


async def _count_subquery(base: dict[str, Any], filter_clause: dict[str, Any]) -> int:
    q: dict[str, Any] = {"bool": {"must": [base], "filter": [filter_clause]}}
    return await _client.count_items(q)


async def _gather_counts(
    base: dict[str, Any],
    items: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, int]]:
    sem = asyncio.Semaphore(_STATS_CONCURRENCY)

    async def _one(key: str, clause: dict[str, Any]) -> tuple[str, int]:
        async with sem:
            return key, await _count_subquery(base, clause)

    return list(await asyncio.gather(*[_one(k, c) for k, c in items]))


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


# --------------------------------------------------------------------------
# Lookup & authority tools
# --------------------------------------------------------------------------


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
        sort=[{"metadata.datePublishedInPrint": {"order": "desc"}}],
    )
    return summarize_search(payload)


# --------------------------------------------------------------------------
# Bibliometric analysis tools (client-side aggregation)
# --------------------------------------------------------------------------


@mcp.tool()
async def publication_statistics(
    query: dict[str, Any] | None = None,
    group_by: str = "year",
    max_records: int | None = None,
    top: int = 20,
) -> dict[str, Any]:
    """Compute distributions over a set of publications.

    `group_by` is one of: "year", "genre", "language", "open_access",
    "organization". `query` is an Elasticsearch query DSL object (default: all
    records).

    For "year", "genre", "language", and "open_access" the counts are derived
    from concurrent count sub-queries (size=0) — no records are fetched, so
    results are exact regardless of dataset size. For "organization", records
    are fetched (all by default; cap with `max_records`).
    """
    q = query or {"match_all": {}}

    if group_by == "year":
        has_date = {"exists": {"field": "metadata.datePublishedInPrint"}}
        dated_q = {"bool": {"must": [q], "filter": [has_date]}}
        oldest, newest = await asyncio.gather(
            _client.search_items(query=dated_q, size=1, sort=[{"metadata.datePublishedInPrint": {"order": "asc"}}]),
            _client.search_items(query=dated_q, size=1, sort=[{"metadata.datePublishedInPrint": {"order": "desc"}}]),
        )

        def _yr(resp: dict[str, Any], fallback: int) -> int:
            recs = resp.get("records") or []
            if not recs:
                return fallback
            val = str(((recs[0].get("data") or recs[0]).get("metadata") or {}).get("datePublishedInPrint") or "")
            return int(val[:4]) if len(val) >= 4 and val[:4].isdigit() else fallback

        min_year = max(_yr(oldest, 1900), 1800)
        max_year = _yr(newest, datetime.now().year)
        year_clauses = [
            (str(yr), {"range": {"metadata.datePublishedInPrint": {
                "gte": f"{yr}||/y", "lte": f"{yr}||/y", "format": "yyyy",
            }}})
            for yr in range(min_year, max_year + 1)
        ]
        raw = await _gather_counts(q, year_clauses)
        buckets = sorted([{"key": k, "count": v} for k, v in raw if v > 0], key=lambda b: b["key"])
        return {
            "groupBy": group_by,
            "totalMatchingRecords": sum(b["count"] for b in buckets),
            "buckets": buckets[:top] if len(buckets) > top else buckets,
            "note": "exact counts via targeted sub-queries",
        }

    elif group_by == "genre":
        raw = await _gather_counts(q, [(g, {"term": {"metadata.genre": g}}) for g in _GENRES])
        buckets = sorted([{"key": k, "count": v} for k, v in raw if v > 0], key=lambda b: -b["count"])
        return {
            "groupBy": group_by,
            "totalMatchingRecords": sum(b["count"] for b in buckets),
            "buckets": buckets[:top],
            "note": "exact counts via targeted sub-queries",
        }

    elif group_by == "language":
        raw = await _gather_counts(q, [(lang, {"term": {"metadata.languages": lang}}) for lang in _LANGUAGES])
        buckets = sorted([{"key": k, "count": v} for k, v in raw if v > 0], key=lambda b: -b["count"])
        return {
            "groupBy": group_by,
            "totalMatchingRecords": sum(b["count"] for b in buckets),
            "buckets": buckets[:top],
            "note": "exact counts via targeted sub-queries",
        }

    elif group_by == "open_access":
        total, oa = await asyncio.gather(
            _client.count_items(q),
            _count_subquery(q, {"term": {"files.visibility": "PUBLIC"}}),
        )
        return {
            "groupBy": group_by,
            "totalMatchingRecords": total,
            "buckets": [
                {"key": "open_access", "count": oa},
                {"key": "closed", "count": max(0, total - oa)},
            ],
            "note": "exact counts via targeted sub-queries",
        }

    else:  # organization — requires fetching records to inspect affiliation names
        records = await _client.fetch_all(q, max_records=max_records)
        result = analysis.distribution(records, group_by=group_by, top=top)
        result["note"] = f"aggregated from {len(records)} fetched records"
        return result


@mcp.tool()
async def coauthorship_analysis(
    query: dict[str, Any] | None = None,
    max_records: int | None = None,
    top: int = 25,
) -> dict[str, Any]:
    """Analyze collaboration patterns across a set of publications.

    Returns average team size, count of solo-authored works, and the top
    collaborating authors and institutions. `query` is an Elasticsearch query
    DSL object (default: all records). Set `max_records` to an integer to limit
    the sample; the default (null) fetches all matching records.
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
    all matching records. Returns a per-author list plus a summary (distinct
    authors, distinct institutions, ORCID coverage).

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
                "familyName": person.get("familyName"),
                "firstName": analysis.clean_given_name(person.get("givenName")),
                "personId": cone_id.rstrip("/").split("/")[-1] if cone_id else None,
                "orcid": None,
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
                    entry["orcid"] = resolved.get("orcid")
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


# --------------------------------------------------------------------------
# Enrichment tools — PuRe is the spine; external public sources hang off the
# identifiers PuRe provides (DOI). All sources are free and require no auth.
# --------------------------------------------------------------------------


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
            if (fmd.get("visibility") or "").upper() == "PUBLIC":
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


def main() -> None:
    """Console-script entry point.

    Defaults to stdio (for local clients like Claude Desktop/Code). Set
    ``MCP_TRANSPORT=http`` (or ``streamable-http``) to serve over Streamable
    HTTP instead — used when hosting a remote connector URL. ``HOST``/``PORT``
    configure the bind address (``PORT`` is provided by most hosting platforms).
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.settings.host = os.getenv("HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("PORT", "8000"))
        mcp.settings.transport_security = _transport_security()
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


def _transport_security() -> "TransportSecuritySettings":
    """Configure the Host/Origin allow-list for HTTP transport.

    The MCP SDK enables DNS-rebinding protection by default, trusting only
    localhost — which rejects a deployed hostname with HTTP 421. We trust the
    platform-provided external hostname (Render sets ``RENDER_EXTERNAL_HOSTNAME``)
    plus anything in ``MCP_ALLOWED_HOSTS`` (comma-separated). If no host can be
    determined, protection is disabled — safe here because the server is public
    and read-only with no auth or local resources to protect.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    hosts = [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    platform_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if platform_host:
        hosts.append(platform_host)
    if not hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    # accept each host with and without an explicit port
    allowed_hosts = ["localhost:*", "127.0.0.1:*"]
    allowed_origins: list[str] = []
    for h in hosts:
        allowed_hosts += [h, f"{h}:*"]
        allowed_origins += [f"https://{h}", f"http://{h}"]
    return TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


if __name__ == "__main__":
    main()
