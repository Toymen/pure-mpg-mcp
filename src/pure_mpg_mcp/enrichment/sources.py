"""Per-provider fetch functions, each returning a trimmed dict or None.

Every function takes the shared httpx client plus a normalized DOI — no
per-source client state, so `Enrichment` just delegates here.
"""

from __future__ import annotations

from typing import Any

import httpx


async def get_json(client: httpx.AsyncClient, url: str, **params: Any) -> dict[str, Any] | None:
    try:
        resp = await client.get(url, params={k: v for k, v in params.items() if v is not None})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError):
        return None


async def openalex(client: httpx.AsyncClient, doi: str, mailto: str) -> dict[str, Any] | None:
    d = await get_json(client, f"https://api.openalex.org/works/https://doi.org/{doi}", mailto=mailto)
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


async def crossref(client: httpx.AsyncClient, doi: str, mailto: str) -> dict[str, Any] | None:
    d = await get_json(client, f"https://api.crossref.org/works/{doi}", mailto=mailto)
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


async def unpaywall(client: httpx.AsyncClient, doi: str, email: str | None) -> dict[str, Any] | None:
    if email is None:  # Unpaywall requires a real, non-example address
        return None
    d = await get_json(client, f"https://api.unpaywall.org/v2/{doi}", email=email)
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


async def semanticscholar(client: httpx.AsyncClient, doi: str) -> dict[str, Any] | None:
    d = await get_json(
        client,
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
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
