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


@mcp.custom_route("/health", methods=["GET", "HEAD"])
async def _health(_request: Any) -> Any:
    """Plain HTTP health check for the hosting platform (the MCP endpoint itself expects the MCP protocol, not a bare GET)."""
    from starlette.responses import PlainTextResponse

    return PlainTextResponse("ok")

# --- publication_statistics: count-based aggregation helpers ---------------

_STATS_CONCURRENCY = 8  # max parallel count requests

# Complete genre vocabulary from the PubMan JSON model.
_GENRES = [
    "ARTICLE", "BLOG_POST", "BOOK", "BOOK_ITEM", "BOOK_REVIEW", "CASE_NOTE",
    "CASE_STUDY", "COLLECTED_EDITION", "COMMENTARY", "CONFERENCE_PAPER",
    "CONFERENCE_REPORT", "CONTRIBUTION_TO_COLLECTED_EDITION",
    "CONTRIBUTION_TO_COMMENTARY", "CONTRIBUTION_TO_ENCYCLOPEDIA",
    "CONTRIBUTION_TO_FESTSCHRIFT", "CONTRIBUTION_TO_HANDBOOK",
    "COURSEWARE_LECTURE", "DATA_PUBLICATION", "EDITORIAL", "ENCYCLOPEDIA",
    "FESTSCHRIFT", "FILM", "HANDBOOK", "INTERVIEW", "ISSUE", "JOURNAL",
    "MAGAZINE_ARTICLE", "MANUAL", "MANUSCRIPT", "MEETING_ABSTRACT",
    "MONOGRAPH", "MULTI_VOLUME", "NEWSPAPER", "NEWSPAPER_ARTICLE", "OPINION",
    "OTHER", "PAPER", "PATENT", "POSTER", "PREPRINT",
    "PRE_REGISTRATION_PAPER", "PROCEEDINGS", "REGISTERED_REPORT", "REPORT",
    "REVIEW_ARTICLE", "SERIES", "SOFTWARE", "TALK_AT_EVENT", "THESIS",
]

_LANGUAGES = [
    "afr", "ara", "aze", "bel", "bos", "bul", "cat", "ces", "cym", "dan",
    "deu", "ell", "eng", "est", "eus", "fas", "fin", "fra", "gle", "glg",
    "heb", "hin", "hrv", "hun", "hye", "ind", "isl", "ita", "jpn", "kat",
    "kor", "lat", "lav", "lit", "mkd", "mlt", "msa", "nld", "nor", "pol",
    "por", "ron", "rus", "slk", "slv", "spa", "srp", "swe", "tha", "tur",
    "ukr", "urd", "vie", "zho",
]

_OA_STATUSES = ["GOLD", "GREEN", "HYBRID", "MISCELLANEOUS", "NOT_SPECIFIED", "CLOSED_ACCESS"]

_DATE_PUBLISHED = ["metadata.datePublishedInPrint", "metadata.datePublishedOnline"]

# Date criteria of the PubMan advanced search, mapped to index fields.
_DATE_FIELDS: dict[str, list[str]] = {
    "any": [
        "metadata.datePublishedInPrint", "metadata.datePublishedOnline",
        "metadata.dateAccepted", "metadata.dateSubmitted",
        "metadata.dateModified", "metadata.dateCreated",
    ],
    "published_in_print": ["metadata.datePublishedInPrint"],
    "published_online": ["metadata.datePublishedOnline"],
    "accepted": ["metadata.dateAccepted"],
    "submitted": ["metadata.dateSubmitted"],
    "modified": ["metadata.dateModified"],
    "created": ["metadata.dateCreated"],
    "modified_internal": ["lastModificationDate"],
    "created_internal": ["creationDate"],
    "event_start": ["metadata.event.startDate"],
    "event_end": ["metadata.event.endDate"],
}


def _range_for(field: str, gte: str | None, lte: str | None) -> dict[str, Any]:
    """Build a range clause; bare years are matched as whole years."""
    rng: dict[str, Any] = {}
    if gte:
        rng["gte"] = f"{gte}||/y" if len(gte) == 4 and gte.isdigit() else gte
    if lte:
        rng["lte"] = f"{lte}||/y" if len(lte) == 4 and lte.isdigit() else lte
    if all(len(v) == 4 and v.isdigit() for v in (gte, lte) if v):
        rng["format"] = "yyyy"
    return {"range": {field: rng}}


def _date_clause(fields: list[str], gte: str | None, lte: str | None) -> dict[str, Any]:
    """Match a date range on any of `fields` (a record matches if one field is in range)."""
    clauses = [_range_for(f, gte, lte) for f in fields]
    if len(clauses) == 1:
        return clauses[0]
    return {"bool": {"should": clauses, "minimum_should_match": 1}}


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


async def _term_distribution(
    q: dict[str, Any], group_by: str, field: str, values: list[str], top: int
) -> dict[str, Any]:
    """Exact per-value counts for a term field, via concurrent count sub-queries."""
    raw = await _gather_counts(q, [(v, {"term": {field: v}}) for v in values])
    buckets = sorted([{"key": k, "count": v} for k, v in raw if v > 0], key=lambda b: -b["count"])
    return {
        "groupBy": group_by,
        "totalMatchingRecords": sum(b["count"] for b in buckets),
        "buckets": buckets[:top],
        "note": "exact counts via targeted sub-queries",
    }


async def _language_codes() -> list[str]:
    """ISO 639-3 codes to check for `publication_statistics(group_by="language")`.

    Sourced live from the CONE authority vocabulary — the authoritative list
    of languages PubMan actually accepts, so it can't drift out of date the
    way a hand-maintained list can. Falls back to the static `_LANGUAGES`
    list if CONE (a separate service from the main REST API) is unreachable.
    """
    try:
        entries = await _cone.languages()
        codes = sorted({e["id"] for e in entries if e.get("id")})
        if codes:
            return codes
    except Exception:  # noqa: BLE001 — CONE is best-effort here; the static list is the fallback
        pass
    return _LANGUAGES


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


# Search criteria that translate straight to a single `match` clause —
# "PuRe field name" -> "ES field path".
_MATCH_FIELDS = {
    "title": "metadata.title",  # "Titel"
    "keyword": "metadata.freeKeywords",  # "Schlagwörter"
    "classification": "metadata.subjects.value",  # "Klassifikation" — controlled subjects
    "source": "metadata.sources.title",  # "Quelle"/"Zeitschrift"
    "local_tag": "localTags",  # "Lokale Tags"
    "event": "metadata.event.title",  # "Titel der Veranstaltung"
}

# Search criteria that translate to a single `term` clause (exact match).
# "PuRe field name" -> (ES field path, uppercase the value first).
_TERM_FIELDS = {
    "genre": ("metadata.genre", True),
    "review_method": ("metadata.reviewMethod", True),  # "Begutachtung" — PEER/INTERNAL/NO_REVIEW
    "language": ("metadata.languages", False),  # ISO 639-3, e.g. "eng", "deu"
}


def _build_search_query(  # noqa: C901 — one clause per search criterion
    text: str | None = None,
    title: str | None = None,
    keyword: str | None = None,
    classification: str | None = None,
    fulltext: str | None = None,
    author: str | None = None,
    orcid: str | None = None,
    organization: str | None = None,
    genre: str | None = None,
    review_method: str | None = None,
    language: str | None = None,
    source: str | None = None,
    identifier: str | None = None,
    local_tag: str | None = None,
    collection: str | None = None,
    project: str | None = None,
    event: str | None = None,
    year: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    date_field: str = "any",
) -> dict[str, Any]:
    """Translate the PubMan advanced-search criteria into an ES bool query."""
    values = locals()
    must: list[dict[str, Any]] = []
    for field, es_field in _MATCH_FIELDS.items():
        if values[field]:
            must.append({"match": {es_field: values[field]}})
    for field, (es_field, upper) in _TERM_FIELDS.items():
        if values[field]:
            must.append({"term": {es_field: values[field].upper() if upper else values[field]}})

    if text:  # "Alle Felder" — all indexed fields
        must.append({"simple_query_string": {"query": text}})
    if fulltext:  # "Volltext" — text extracted from attached files
        must.append(
            {
                "simple_query_string": {
                    "query": fulltext,
                    "fields": ["fulltext", "fulltexts", "fileData.content", "files.fileData.content"],
                    "lenient": True,
                }
            }
        )
    if author:  # "Urheber" — family or given name
        must.append(
            {
                "multi_match": {
                    "query": author,
                    "fields": [
                        "metadata.creators.person.familyName",
                        "metadata.creators.person.givenName",
                    ],
                }
            }
        )
    if orcid:  # bare id or orcid.org URL
        must.append({"match": {"metadata.creators.person.orcid": orcid.rstrip("/").split("/")[-1]}})
    if organization:  # "Organisation" — OU id (incl. sub-units via identifierPath) or name
        if organization.startswith("ou_"):
            must.append(
                {
                    "bool": {
                        "should": [
                            {"term": {"metadata.creators.person.organizations.identifier": organization}},
                            {"term": {"metadata.creators.person.organizations.identifierPath": organization}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )
        else:
            must.append({"match": {"metadata.creators.person.organizations.name": organization}})
    if identifier:  # "Identifikatoren" — DOI, ISBN, ISSN, arXiv, PMID, …
        must.append(
            {
                "bool": {
                    "should": [
                        {"term": {"metadata.identifiers.id.keyword": identifier}},
                        {"match_phrase": {"metadata.identifiers.id": identifier}},
                        {"match_phrase": {"metadata.sources.identifiers.id": identifier}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    if collection:  # "Kontext" — context id like ctx_123456
        must.append({"term": {"context.objectId": collection}})
    if project:  # "Projekt-Information" — title, grant id, funder, or program
        must.append(
            {
                "bool": {
                    "should": [
                        {"match": {"metadata.projectInfo.title": project}},
                        {"match": {"metadata.projectInfo.grantIdentifier": project}},
                        {"match": {"metadata.projectInfo.fundingInfo.fundingOrganization.title": project}},
                        {"match": {"metadata.projectInfo.fundingInfo.fundingProgram.title": project}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    if year:
        must.append(_date_clause(_DATE_PUBLISHED, str(year), str(year)))
    if date_from or date_to:
        fields = _DATE_FIELDS.get(date_field)
        if fields is None:
            raise ValueError(f"unknown date_field: {date_field!r} (one of {sorted(_DATE_FIELDS)})")
        must.append(_date_clause(fields, date_from, date_to))
    return {"bool": {"must": must}} if must else {"match_all": {}}


@mcp.tool()
async def search_publications(
    text: str | None = None,
    title: str | None = None,
    keyword: str | None = None,
    classification: str | None = None,
    fulltext: str | None = None,
    author: str | None = None,
    orcid: str | None = None,
    organization: str | None = None,
    genre: str | None = None,
    review_method: str | None = None,
    language: str | None = None,
    source: str | None = None,
    identifier: str | None = None,
    local_tag: str | None = None,
    collection: str | None = None,
    project: str | None = None,
    event: str | None = None,
    year: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    date_field: str = "any",
    size: int = 10,
    offset: int = 0,
    full_records: bool = False,
) -> dict[str, Any]:
    """Search Max Planck publications in PuRe (all advanced-search criteria).

    Most user requests to this tool will be in German — the PuRe advanced-search
    UI field names are given below so German terms map straight to a parameter.

    Every filter of the PuRe advanced search is available; combine freely
    (all conditions must match):
      `text` all fields (Alle Felder) | `title` (Titel) |
      `keyword` (Schlagwörter/freeKeywords) |
      `classification` (Klassifikation — controlled subjects) |
      `fulltext` (Volltext — attached file text) |
      `author` (Urheber — creator name) | `orcid` (ORCID) |
      `organization` (Organisation — name, or an ou_… id — ids also match
      publications of all sub-units) | `genre` (Genre; e.g. ARTICLE, PREPRINT,
      THESIS) | `review_method` (Begutachtung — PEER/INTERNAL/NO_REVIEW) |
      `language` (Sprachen — ISO 639-3, e.g. deu, eng) |
      `source` (Quelle/Zeitschrift — journal/book title) |
      `identifier` (Identifikatoren — DOI, ISBN, arXiv, …) |
      `local_tag` (Lokale Tags) | `collection` (Kontext — ctx_… id) |
      `project` (Projekt-Information) | `event` (Titel der Veranstaltung).

    Dates (Datum): `year` matches the publication year (print or online). For
    other ranges use `date_from`/`date_to` (YYYY or YYYY-MM-DD) with
    `date_field`: any (Datum), published_in_print (Erschienen), published_online
    (Online veröffentlicht), accepted (Angenommen), submitted (Eingereicht),
    modified (Geändert), created (Erstellt), modified_internal
    (Änderungsdatum (technisch)), created_internal (Erstellungsdatum
    (technisch)), event_start (Veranstaltungsbeginn), event_end
    (Veranstaltungsende).

    Returns numberOfRecords plus compact item summaries (set
    `full_records=True` for raw records). Fetch full metadata for a hit with
    `get_publication(itemId)`.
    """
    query = _build_search_query(
        text=text, title=title, keyword=keyword, classification=classification,
        fulltext=fulltext, author=author, orcid=orcid, organization=organization,
        genre=genre, review_method=review_method, language=language, source=source,
        identifier=identifier, local_tag=local_tag, collection=collection,
        project=project, event=event, year=year,
        date_from=date_from, date_to=date_to, date_field=date_field,
    )
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
async def get_organization(ou_id: str) -> dict[str, Any]:
    """Get one Max Planck organizational unit by id (e.g. "ou_1234567")."""
    return await _client.get_ou(ou_id)


@mcp.tool()
async def list_top_organizations() -> dict[str, Any]:
    """List the top-level (root) Max Planck organizational units."""
    return await _client.ous_toplevel()


@mcp.tool()
async def list_first_level_organizations() -> dict[str, Any]:
    """List the first-level Max Planck organizational units (below the roots)."""
    return await _client.ous_firstlevel()


@mcp.tool()
async def organization_children(ou_id: str) -> Any:
    """List the direct child organizational units of an OU (e.g. departments of an institute)."""
    return await _client.ou_children(ou_id)


@mcp.tool()
async def organization_hierarchy(ou_id: str) -> dict[str, Any]:
    """Get the ancestor path of an OU, from itself up to the root institute.

    Useful to resolve which institute a department or sub-unit belongs to.
    Returns both the id path and the human-readable name path.
    """
    ids, names = await asyncio.gather(_client.ou_id_path(ou_id), _client.ou_name_path(ou_id))
    return {"ouId": ou_id, "idPath": ids, "namePath": names}


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
    "oa_status" (GOLD/GREEN/HYBRID/MISCELLANEOUS/NOT_SPECIFIED/CLOSED_ACCESS),
    "organization". `query` is an Elasticsearch query DSL object (default: all
    records).

    For "year" (bracketed across print and online publication dates), "genre",
    "language" (codes sourced live from the CONE authority; see `list_languages`),
    "open_access", and "oa_status" the counts are derived from concurrent count
    sub-queries (size=0) — no records are fetched, so results are exact
    regardless of dataset size. For "organization", records are fetched (all
    by default; cap with `max_records`) and every creator role counts, not
    just authors/editors.
    """
    q = query or {"match_all": {}}

    if group_by == "year":
        # A publication's year may only be recorded online (preprints, recent
        # articles ahead of print) — bracket the range across both date fields.
        bounds = await asyncio.gather(
            *[
                _client.search_items(
                    query={"bool": {"must": [q], "filter": [{"exists": {"field": f}}]}},
                    size=1, sort=[{f: {"order": order}}],
                )
                for f in _DATE_PUBLISHED
                for order in ("asc", "desc")
            ]
        )

        def _yr(resp: dict[str, Any], field: str) -> int | None:
            recs = resp.get("records") or []
            if not recs:
                return None
            val = str(((recs[0].get("data") or recs[0]).get("metadata") or {}).get(field) or "")
            return int(val[:4]) if len(val) >= 4 and val[:4].isdigit() else None

        years = [
            y
            for resp, field in zip(bounds, [f for f in _DATE_PUBLISHED for _ in (0, 1)])
            if (y := _yr(resp, field)) is not None
        ]
        min_year = max(min(years, default=1900), 1800)
        max_year = max(years, default=datetime.now().year)
        year_clauses = [
            (str(yr), _date_clause(_DATE_PUBLISHED, str(yr), str(yr)))
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
        return await _term_distribution(q, group_by, "metadata.genre", _GENRES, top)

    elif group_by == "language":
        return await _term_distribution(q, group_by, "metadata.languages", await _language_codes(), top)

    elif group_by == "open_access":
        # A public file whose oaStatus is explicitly CLOSED_ACCESS is a locator
        # pointing at a paywalled page, not an open-access copy.
        oa_filter = {
            "bool": {
                "must": [{"term": {"files.visibility": "PUBLIC"}}],
                "must_not": [{"term": {"files.oaStatus": "CLOSED_ACCESS"}}],
            }
        }
        total, oa = await asyncio.gather(
            _client.count_items(q),
            _count_subquery(q, oa_filter),
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

    elif group_by == "oa_status":
        return await _term_distribution(q, group_by, "files.oaStatus", _OA_STATUSES, top)

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
    EDITOR, TRANSLATOR, DIRECTOR, REFEREE, INVENTOR, ...) — each entry carries
    its `role` plus `personId`/`orcid` so grouping, filtering, or dedup by
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
