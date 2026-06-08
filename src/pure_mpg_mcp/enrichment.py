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

SOURCES = ("openalex", "crossref", "unpaywall", "semanticscholar")


def _contact_email() -> str:
    return os.getenv("PURE_CONTACT_EMAIL", "pure-mpg-mcp@example.com")


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
            headers={"User-Agent": f"pure-mpg-mcp ({_contact_email()})", "Accept": "application/json"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_json(self, url: str, **params: Any) -> dict[str, Any] | None:
        try:
            resp = await self._client.get(url, params={k: v for k, v in params.items() if v is not None})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError):
            return None

    # --- individual sources (all return a trimmed dict or None) -----------

    async def openalex(self, doi: str) -> dict[str, Any] | None:
        d = await self._get_json(
            f"https://api.openalex.org/works/https://doi.org/{normalize_doi(doi)}",
            mailto=_contact_email(),
        )
        if not d:
            return None
        institutions = sorted(
            {
                i.get("display_name")
                for a in (d.get("authorships") or [])
                for i in (a.get("institutions") or [])
                if i.get("display_name")
            }
        )
        ror_ids = sorted(
            {
                i.get("ror")
                for a in (d.get("authorships") or [])
                for i in (a.get("institutions") or [])
                if i.get("ror")
            }
        )
        return {
            "openalex_id": d.get("id"),
            "cited_by_count": d.get("cited_by_count"),
            "oa_status": (d.get("open_access") or {}).get("oa_status"),
            "topics": [t.get("display_name") for t in (d.get("topics") or [])[:5]],
            "institutions": institutions[:10],
            "ror_ids": ror_ids[:10],
            "referenced_works_count": len(d.get("referenced_works") or []),
            "related_works": (d.get("related_works") or [])[:5],
        }

    async def crossref(self, doi: str) -> dict[str, Any] | None:
        d = await self._get_json(
            f"https://api.crossref.org/works/{normalize_doi(doi)}", mailto=_contact_email()
        )
        if not d or "message" not in d:
            return None
        m = d["message"]
        return {
            "is_referenced_by_count": m.get("is-referenced-by-count"),
            "references_count": m.get("references-count"),
            "funders": [f.get("name") for f in (m.get("funder") or [])],
            "license": [lic.get("URL") for lic in (m.get("license") or [])],
            "subjects": m.get("subject") or [],
            "publisher": m.get("publisher"),
            "container": (m.get("container-title") or [None])[0],
        }

    async def unpaywall(self, doi: str) -> dict[str, Any] | None:
        d = await self._get_json(
            f"https://api.unpaywall.org/v2/{normalize_doi(doi)}", email=_contact_email()
        )
        if not d:
            return None
        loc = d.get("best_oa_location") or {}
        return {
            "is_oa": d.get("is_oa"),
            "oa_status": d.get("oa_status"),
            "best_oa_url": loc.get("url"),
            "best_oa_pdf": loc.get("url_for_pdf"),
            "host_type": loc.get("host_type"),
            "license": loc.get("license"),
        }

    async def semanticscholar(self, doi: str) -> dict[str, Any] | None:
        d = await self._get_json(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{normalize_doi(doi)}",
            fields="citationCount,influentialCitationCount,tldr,fieldsOfStudy",
        )
        if not d:
            return None
        tldr = d.get("tldr") or {}
        return {
            "citation_count": d.get("citationCount"),
            "influential_citation_count": d.get("influentialCitationCount"),
            "fields_of_study": d.get("fieldsOfStudy") or [],
            "tldr": tldr.get("text"),
        }

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
