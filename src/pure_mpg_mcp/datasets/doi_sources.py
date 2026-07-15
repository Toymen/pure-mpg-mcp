"""DOI-keyed fetchers: which datasets are linked to this publication DOI?

Each returns a list of normalized hits (possibly empty = queried fine, none
found) or None (provider unreachable). Endpoints and their quirks are
documented in docs/research-data-discovery.md, all verified live.
"""

from __future__ import annotations

from typing import Any

import httpx

from .common import get_json, hit, strip_doi_url, year_of

SCHOLIX_URL = "https://api.scholexplorer.openaire.eu/v2/Links"


def _scholix_hit(link: dict[str, Any], side: str) -> dict[str, Any]:
    obj = link[side]
    dois = [i.get("ID") for i in obj.get("Identifier") or [] if (i.get("IDScheme") or "").lower() == "doi"]
    publishers = [p.get("name") for p in obj.get("Publisher") or [] if p.get("name")]
    return hit(
        doi=dois[0] if dois else None,
        title=obj.get("Title"),
        publisher=publishers[0] if publishers else None,
        relation=(link.get("RelationshipType") or {}).get("Name"),
    )


async def scholexplorer(client: httpx.AsyncClient, doi: str) -> list[dict[str, Any]] | None:
    """Scholix links in both directions — repository-deposited `IsSupplementTo`
    links usually point dataset->article and are invisible from the source side."""
    directions = (
        ({"sourcePid": doi, "targetType": "dataset"}, "target"),
        ({"targetPid": doi, "sourceType": "dataset"}, "source"),
    )
    hits: list[dict[str, Any]] = []
    reachable = False
    seen: set[str] = set()
    for params, side in directions:
        d = await get_json(client, SCHOLIX_URL, **params)
        if d is None:
            continue
        reachable = True
        for link in d.get("result") or []:
            h = _scholix_hit(link, side)
            key = (h["doi"] or h["title"] or "").lower()
            if key and key not in seen:
                seen.add(key)
                hits.append(h)
    return hits if reachable else None


def parse_datacite(d: dict[str, Any] | None, doi: str | None = None) -> list[dict[str, Any]] | None:
    if d is None or "data" not in d:
        return None
    hits = []
    for item in d["data"]:
        a = item.get("attributes") or {}
        publisher = a.get("publisher")
        if isinstance(publisher, dict):  # schema 4.5 publishers are objects
            publisher = publisher.get("name")
        relation = next(
            (
                r.get("relationType")
                for r in a.get("relatedIdentifiers") or []
                if doi and (r.get("relatedIdentifier") or "").lower() == doi.lower()
            ),
            None,
        )
        titles = a.get("titles") or []
        hits.append(
            hit(
                doi=item.get("id"),
                title=titles[0].get("title") if titles else None,
                publisher=publisher,
                year=a.get("publicationYear"),
                relation=relation,
            )
        )
    return hits


async def datacite(client: httpx.AsyncClient, doi: str) -> list[dict[str, Any]] | None:
    d = await get_json(
        client,
        "https://api.datacite.org/dois",
        query=f'relatedIdentifiers.relatedIdentifier:"{doi}"',
        **{"resource-type-id": "dataset", "page[size]": 25},
    )
    return parse_datacite(d, doi)


async def b2find(client: httpx.AsyncClient, doi: str) -> list[dict[str, Any]] | None:
    d = await get_json(
        client, "https://b2find.eudat.eu/api/3/action/package_search", q=f'"{doi}"', rows=25
    )
    if d is None or not d.get("success"):
        return None
    hits = []
    for pkg in (d.get("result") or {}).get("results") or []:
        extras = {e.get("key"): e.get("value") for e in pkg.get("extras") or []}
        hits.append(
            hit(
                doi=strip_doi_url(extras.get("DOI")),
                title=pkg.get("title"),
                publisher=extras.get("Publisher"),
                year=year_of(extras.get("PublicationYear")),
            )
        )
    return hits


async def crossref(client: httpx.AsyncClient, doi: str, mailto: str) -> list[dict[str, Any]] | None:
    """Cheap pre-check: publisher-deposited `is-supplemented-by` relations."""
    d = await get_json(client, f"https://api.crossref.org/works/{doi}", mailto=mailto)
    if d is None or "message" not in d:
        return None
    supplements = (d["message"].get("relation") or {}).get("is-supplemented-by") or []
    return [
        hit(doi=s.get("id"), relation="is-supplemented-by")
        for s in supplements
        if (s.get("id-type") or "").lower() == "doi"
    ]


def parse_zenodo(d: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    if d is None or "hits" not in d:
        return None
    return [
        hit(
            doi=rec.get("doi"),
            title=(rec.get("metadata") or {}).get("title"),
            publisher="Zenodo",
            year=year_of((rec.get("metadata") or {}).get("publication_date")),
        )
        for rec in d["hits"].get("hits") or []
    ]


async def zenodo(client: httpx.AsyncClient, doi: str) -> list[dict[str, Any]] | None:
    d = await get_json(
        client,
        "https://zenodo.org/api/records",
        q=f'related.identifier:"{doi}"',
        type="dataset",
        size=25,
    )
    return parse_zenodo(d)


def parse_figshare(items: Any) -> list[dict[str, Any]] | None:
    if not isinstance(items, list):
        return None
    return [
        hit(
            doi=i.get("doi"),
            title=i.get("title"),
            publisher="figshare",
            year=year_of(i.get("published_date")),
        )
        for i in items
    ]


async def figshare(client: httpx.AsyncClient, doi: str) -> list[dict[str, Any]] | None:
    items = await get_json(
        client, "https://api.figshare.com/v2/articles", resource_doi=doi, page_size=25
    )
    return parse_figshare(items)


async def dryad(client: httpx.AsyncClient, doi: str) -> list[dict[str, Any]] | None:
    """Dryad's `q` search is fuzzy — keep only hits whose relatedWorks actually
    reference the queried DOI."""
    d = await get_json(client, "https://datadryad.org/api/v2/search", q=f'"{doi}"', per_page=25)
    if d is None or "_embedded" not in d:
        return None
    hits = []
    for ds in d["_embedded"].get("stash:datasets") or []:
        related = [(w.get("identifier") or "").lower() for w in ds.get("relatedWorks") or []]
        if doi.lower() not in related:
            continue
        hits.append(
            hit(
                doi=strip_doi_url(ds.get("identifier")),
                title=ds.get("title"),
                publisher="Dryad",
                year=year_of(ds.get("publicationDate")),
            )
        )
    return hits
