"""Translate the PubMan advanced-search criteria into an Elasticsearch bool query."""

from __future__ import annotations

from typing import Any

from . import search_clauses as clauses
from .vocab import _DATE_FIELDS, _DATE_PUBLISHED, _MATCH_FIELDS, _TERM_FIELDS


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
    range_clauses = [_range_for(f, gte, lte) for f in fields]
    if len(range_clauses) == 1:
        return range_clauses[0]
    return {"bool": {"should": range_clauses, "minimum_should_match": 1}}


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
    if fulltext:
        must.append(clauses.fulltext_clause(fulltext))
    if author:
        must.append(clauses.author_clause(author))
    if orcid:  # bare id or orcid.org URL
        must.append({"match": {"metadata.creators.person.orcid": orcid.rstrip("/").split("/")[-1]}})
    if organization:
        must.append(clauses.organization_clause(organization))
    if identifier:
        must.append(clauses.identifier_clause(identifier))
    if collection:  # "Kontext" — context id like ctx_123456
        must.append({"term": {"context.objectId": collection}})
    if project:
        must.append(clauses.project_clause(project))
    if year:
        must.append(_date_clause(_DATE_PUBLISHED, str(year), str(year)))
    if date_from or date_to:
        fields = _DATE_FIELDS.get(date_field)
        if fields is None:
            raise ValueError(f"unknown date_field: {date_field!r} (one of {sorted(_DATE_FIELDS)})")
        must.append(_date_clause(fields, date_from, date_to))
    return {"bool": {"must": must}} if must else {"match_all": {}}
