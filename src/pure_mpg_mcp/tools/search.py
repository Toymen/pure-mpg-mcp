"""Publication search tools."""

from __future__ import annotations

from typing import Any

from ..context import _client, mcp
from ..models import summarize_search
from ..search_query import _build_search_query


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
