"""Helpers to trim verbose PuRe responses into compact, model-friendly shapes.

The raw PuRe item records are large (full eSciDoc metadata). For most agent
use cases a compact summary is enough; callers can always fetch the full
record with ``get_publication`` when they need everything.
"""

from __future__ import annotations

from typing import Any


def _creators(md: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for c in md.get("creators", []) or []:
        person = c.get("person") or {}
        name = person.get("familyName")
        given = person.get("givenName")
        if name and given:
            out.append(f"{name}, {given}")
        elif name:
            out.append(name)
        else:
            org = (c.get("organization") or {}).get("name")
            if org:
                out.append(org)
    return out


def summarize_item(record: dict[str, Any]) -> dict[str, Any]:
    """Reduce one search-result record (or full item) to key fields."""
    data = record.get("data", record)
    md = data.get("metadata", {}) or {}
    files = []
    for comp in data.get("files", []) or []:
        fmd = comp.get("metadata", {}) or {}
        files.append(
            {
                "componentId": comp.get("objectId"),
                "name": fmd.get("title") or fmd.get("name"),
                "mimeType": comp.get("mimeType") or fmd.get("mimeType"),
                "visibility": comp.get("visibility") or fmd.get("visibility"),
                "oaStatus": comp.get("oaStatus") or fmd.get("oaStatus"),
                "storage": comp.get("storage"),
            }
        )
    return {
        "itemId": data.get("objectId"),
        "title": md.get("title"),
        "creators": _creators(md),
        "genre": md.get("genre"),
        "datePublished": md.get("datePublishedInPrint") or md.get("datePublishedOnline"),
        "doi": _first_identifier(md, "DOI"),
        "pid": data.get("objectPid"),
        "publicState": data.get("publicState"),
        "files": files,
    }


def _first_identifier(md: dict[str, Any], id_type: str) -> str | None:
    for ident in md.get("identifiers", []) or []:
        if ident.get("type", "").upper().endswith(id_type):
            return ident.get("id")
    return None


def summarize_search(payload: dict[str, Any], include_raw: bool = False) -> dict[str, Any]:
    """Compact a /items/search response."""
    records = payload.get("records", []) or []
    return {
        "numberOfRecords": payload.get("numberOfRecords"),
        "scrollId": payload.get("scrollId"),
        "items": payload.get("records") if include_raw else [summarize_item(r) for r in records],
    }
