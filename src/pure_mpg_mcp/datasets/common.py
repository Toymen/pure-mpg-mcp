"""Small shared helpers for the research-data provider fetchers."""

from __future__ import annotations

from typing import Any

import httpx

from ..enrichment.sources import get_json

__all__ = ["get_json", "post_json", "hit", "year_of", "strip_doi_url"]


async def post_json(client: httpx.AsyncClient, url: str, body: Any) -> Any | None:
    try:
        resp = await client.post(url, json=body)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError):
        return None


def hit(
    doi: str | None,
    title: str | None = None,
    publisher: str | None = None,
    year: int | None = None,
    relation: str | None = None,
) -> dict[str, Any]:
    """The normalized dataset hit every provider returns."""
    return {"doi": doi, "title": title, "publisher": publisher, "year": year, "relation": relation}


def year_of(date: str | None) -> int | None:
    """Year from an ISO-ish date string ('2020-01-02...') or None."""
    if date and date[:4].isdigit():
        return int(date[:4])
    return None


def strip_doi_url(value: str | None) -> str | None:
    if not value:
        return None
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            return value[len(prefix):]
    return value
