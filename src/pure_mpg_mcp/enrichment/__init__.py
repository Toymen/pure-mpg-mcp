"""Enrichment connectors for public scholarly APIs, keyed off PuRe identifiers.

PuRe is the spine: these connectors take a DOI (which a PuRe record provides)
and attach external signals — citation counts, research topics, open-access
locations, funders. They are *enrichment only*; none of them is queried on its
own, and the canonical record always remains the PuRe item.

All sources are free and require no authentication. Following each provider's
etiquette, a contact email is sent in the "polite pool" / required `email`
param; configure it with ``PURE_CONTACT_EMAIL`` (Unpaywall in particular
requires a real address).

Sources:
  * OpenAlex          https://api.openalex.org      (citations, topics, ROR, OA)
  * Crossref          https://api.crossref.org      (references, funders, license)
  * Unpaywall         https://api.unpaywall.org     (OA status + free full text)
  * Semantic Scholar  https://api.semanticscholar.org (influential citations, TLDR)
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from . import sources as _sources

SOURCES = ("openalex", "crossref", "unpaywall", "semanticscholar")

# Used only for the OpenAlex/Crossref "polite pool" (a courtesy header, not
# validated). Unpaywall, by contrast, *requires* a real address and rejects
# unset/example values — so it falls back to ``contact_email()`` and is skipped
# when that is not configured.
DEFAULT_POLITE_EMAIL = "pure-mpg-mcp@users.noreply.github.com"


def contact_email() -> str | None:
    """A real contact email if configured, else None.

    ``example.com`` addresses are treated as unset because Unpaywall rejects
    them (HTTP 422).
    """
    email = os.getenv("PURE_CONTACT_EMAIL", "").strip()
    if not email or email.lower().endswith("@example.com"):
        return None
    return email


def _polite_email() -> str:
    return contact_email() or DEFAULT_POLITE_EMAIL


def unavailable_sources(sources: list[str]) -> dict[str, str]:
    """Report sources that cannot run with the current configuration."""
    notes: dict[str, str] = {}
    if "unpaywall" in sources and contact_email() is None:
        notes["unpaywall"] = (
            "skipped: set PURE_CONTACT_EMAIL to a real address "
            "(Unpaywall rejects unset/example.com emails)"
        )
    return notes


def normalize_doi(doi: str) -> str:
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
    return doi


class Enrichment:
    """Async connectors over the public scholarly APIs (one shared client)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": f"pure-mpg-mcp ({_polite_email()})", "Accept": "application/json"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_json(self, url: str, **params: Any) -> dict[str, Any] | None:
        return await _sources.get_json(self._client, url, **params)

    # --- individual sources (all return a trimmed dict or None) -----------

    async def openalex(self, doi: str) -> dict[str, Any] | None:
        return await _sources.openalex(self._client, normalize_doi(doi), _polite_email())

    async def crossref(self, doi: str) -> dict[str, Any] | None:
        return await _sources.crossref(self._client, normalize_doi(doi), _polite_email())

    async def unpaywall(self, doi: str) -> dict[str, Any] | None:
        return await _sources.unpaywall(self._client, normalize_doi(doi), contact_email())

    async def semanticscholar(self, doi: str) -> dict[str, Any] | None:
        return await _sources.semanticscholar(self._client, normalize_doi(doi))

    async def fetch(self, doi: str, sources: list[str]) -> dict[str, Any]:
        """Fetch the requested sources for a DOI; missing sources are omitted."""
        out: dict[str, Any] = {}
        for src in sources:
            fn = getattr(self, src, None)
            if fn is None:
                continue
            result = await fn(doi)
            if result is not None:
                out[src] = result
        return out
