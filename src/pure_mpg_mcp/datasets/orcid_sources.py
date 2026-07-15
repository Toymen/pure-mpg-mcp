"""ORCID-keyed fetchers: which datasets has this researcher published?

Same contract as doi_sources: list of normalized hits, empty list = none
found, None = provider unreachable.
"""

from __future__ import annotations

from typing import Any

import httpx

from .common import get_json, hit, post_json, strip_doi_url, year_of
from .doi_sources import parse_datacite, parse_figshare, parse_zenodo


async def datacite(client: httpx.AsyncClient, orcid: str) -> list[dict[str, Any]] | None:
    d = await get_json(
        client,
        "https://api.datacite.org/dois",
        query=f'creators.nameIdentifiers.nameIdentifier:"https://orcid.org/{orcid}"',
        **{"resource-type-id": "dataset", "page[size]": 25},
    )
    return parse_datacite(d)


async def openaire(client: httpx.AsyncClient, orcid: str) -> list[dict[str, Any]] | None:
    d = await get_json(
        client,
        "https://api.openaire.eu/graph/v1/researchProducts",
        authorOrcid=orcid,
        type="dataset",
        pageSize=25,
    )
    if d is None or "results" not in d:
        return None
    hits = []
    for r in d["results"]:
        dois = [p.get("value") for p in r.get("pids") or [] if (p.get("scheme") or "").lower() == "doi"]
        hits.append(
            hit(
                doi=dois[0] if dois else None,
                title=r.get("mainTitle"),
                publisher=r.get("publisher"),
                year=year_of(r.get("publicationDate")),
            )
        )
    return hits


async def openalex(client: httpx.AsyncClient, orcid: str, mailto: str) -> list[dict[str, Any]] | None:
    d = await get_json(
        client,
        "https://api.openalex.org/works",
        filter=f"type:dataset,authorships.author.orcid:{orcid}",
        mailto=mailto,
        **{"per-page": 25},
    )
    if d is None or "results" not in d:
        return None
    return [
        hit(
            doi=strip_doi_url(r.get("doi")),
            title=r.get("display_name"),
            year=r.get("publication_year"),
        )
        for r in d["results"]
    ]


async def zenodo(client: httpx.AsyncClient, orcid: str) -> list[dict[str, Any]] | None:
    d = await get_json(
        client,
        "https://zenodo.org/api/records",
        q=f'creators.orcid:"{orcid}"',
        type="dataset",
        size=25,
    )
    return parse_zenodo(d)


async def figshare(client: httpx.AsyncClient, orcid: str) -> list[dict[str, Any]] | None:
    items = await post_json(
        client,
        "https://api.figshare.com/v2/articles/search",
        {"search_for": f":orcid: {orcid}", "item_type": 3, "page_size": 25},  # 3 = dataset
    )
    return parse_figshare(items)
