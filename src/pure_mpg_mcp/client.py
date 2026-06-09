"""Thin async HTTP client for the public PuRe (PubMan) REST API.

Wraps https://pure.mpg.de/rest — read-only, anonymous (public) access only.
No authentication is performed; only endpoints that serve RELEASED, publicly
visible records are reachable through this client.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://pure.mpg.de/rest"
USER_AGENT = "pure-mpg-mcp/0.1 (+https://github.com/)"


class PureClient:
    """Minimal async wrapper over the PuRe REST API (public read surface)."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("PURE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "PureClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # --- low-level helpers -------------------------------------------------

    async def _get(self, path: str, **params: Any) -> httpx.Response:
        clean = {k: v for k, v in params.items() if v is not None}
        resp = await self._client.get(path, params=clean)
        resp.raise_for_status()
        return resp

    async def _post_json(self, path: str, json_body: Any, **params: Any) -> httpx.Response:
        clean = {k: v for k, v in params.items() if v is not None}
        resp = await self._client.post(path, params=clean, json=json_body)
        resp.raise_for_status()
        return resp

    # --- items -------------------------------------------------------------

    async def search_items(
        self,
        query: dict[str, Any],
        size: int = 10,
        from_: int = 0,
        sort: list[dict[str, Any]] | None = None,
        scroll: bool | None = None,
        format: str | None = None,
        search_after: list[Any] | None = None,
    ) -> dict[str, Any]:
        """POST /items/search — Elasticsearch query DSL over public items."""
        body: dict[str, Any] = {"query": query, "size": size, "from": from_}
        if sort:
            body["sort"] = sort
        if search_after is not None:
            body["search_after"] = search_after
        resp = await self._post_json("/items/search", body, scroll=scroll, format=format)
        return resp.json()

    async def scroll_items(self, scroll_id: str, format: str | None = None) -> dict[str, Any]:
        """GET /items/search/scroll — continue a scrolled search."""
        resp = await self._get("/items/search/scroll", scrollId=scroll_id, format=format)
        return resp.json()

    async def get_item(self, item_id: str) -> dict[str, Any]:
        """GET /items/{itemId} — full metadata for one publication item."""
        resp = await self._get(f"/items/{item_id}")
        return resp.json()

    async def find_by_doi(self, doi: str) -> dict[str, Any]:
        """Find the item whose identifier matches a DOI."""
        doi = doi.strip()
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        query = {
            "bool": {
                "should": [
                    {"term": {"metadata.identifiers.id.keyword": doi}},
                    {"match_phrase": {"metadata.identifiers.id": doi}},
                ],
                "minimum_should_match": 1,
            }
        }
        return await self.search_items(query=query, size=5)

    # Stable sort for search_after keyset pagination — objectId is unique and
    # monotonically assigned, so it makes a safe, gap-free cursor.
    _FETCH_SORT: list[dict[str, Any]] = [{"objectId.keyword": {"order": "asc"}}]

    async def fetch_all(
        self,
        query: dict[str, Any],
        max_records: int | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch records using search_after keyset pagination.

        Bypasses the server-side scroll window cap (typically 1 000 records)
        by issuing a fresh query for each page, using the last record's
        objectId as the cursor. Pass ``max_records=None`` (the default) to
        retrieve every matching record; pass a positive integer to cap the
        result.
        """
        effective_size = min(page_size, max_records) if max_records is not None else page_size
        first = await self.search_items(query=query, size=effective_size, sort=self._FETCH_SORT)
        records: list[dict[str, Any]] = list(first.get("records", []) or [])
        total = first.get("numberOfRecords", len(records))
        limit = max_records if max_records is not None else total

        while len(records) < min(limit, total):
            last_id = (records[-1].get("data") or records[-1]).get("objectId")
            if not last_id:
                break
            page = await self.search_items(
                query=query,
                size=effective_size,
                sort=self._FETCH_SORT,
                search_after=[last_id],
            )
            batch = page.get("records", []) or []
            if not batch:
                break
            records.extend(batch)

        return records[:max_records] if max_records is not None else records

    async def export_item(
        self,
        item_id: str,
        format: str = "BibTex",
        citation: str | None = None,
        csl_cone_id: str | None = None,
    ) -> str:
        """GET /items/{itemId}/export — formatted export (BibTex, citation, etc.)."""
        resp = await self._get(
            f"/items/{item_id}/export",
            format=format,
            citation=citation,
            cslConeId=csl_cone_id,
        )
        return resp.text

    async def get_component_metadata(self, item_id: str, component_id: str) -> dict[str, Any]:
        """GET /items/{itemId}/component/{componentId}/metadata — file metadata."""
        resp = await self._get(f"/items/{item_id}/component/{component_id}/metadata")
        return resp.json()

    # --- organizational units ---------------------------------------------

    async def search_ous(self, query: dict[str, Any], size: int = 10, from_: int = 0) -> dict[str, Any]:
        """POST /ous/search — search organizational units (institutes)."""
        body = {"query": query, "size": size, "from": from_}
        resp = await self._post_json("/ous/search", body)
        return resp.json()

    async def get_ou(self, ou_id: str) -> dict[str, Any]:
        """GET /ous/{ouId} — one organizational unit."""
        resp = await self._get(f"/ous/{ou_id}")
        return resp.json()

    async def ous_toplevel(self) -> dict[str, Any]:
        """GET /ous/toplevel — root-level organizational units."""
        resp = await self._get("/ous/toplevel")
        return resp.json()

    # --- contexts (collections) -------------------------------------------

    async def search_contexts(self, query: dict[str, Any], size: int = 10, from_: int = 0) -> dict[str, Any]:
        """POST /contexts/search — search contexts (collections)."""
        body = {"query": query, "size": size, "from": from_}
        resp = await self._post_json("/contexts/search", body)
        return resp.json()

    # --- feeds & service ---------------------------------------------------

    async def feed_recent(self) -> str:
        """GET /feed/recent — RSS/Atom feed of recently released items."""
        resp = await self._get("/feed/recent")
        return resp.text

    async def feed_open_access(self) -> str:
        """GET /feed/oa — feed of recent open-access items."""
        resp = await self._get("/feed/oa")
        return resp.text

    async def service_info(self) -> dict[str, Any]:
        """GET /miscellaneous/serviceInfo — version / status of the instance.

        Anonymous callers may receive an empty body (detailed info is gated);
        in that case we report reachability rather than failing.
        """
        resp = await self._get("/miscellaneous/serviceInfo")
        text = resp.text.strip()
        if not text:
            return {"status": "ok", "httpStatus": resp.status_code, "detail": "empty (auth required for details)"}
        try:
            return resp.json()
        except ValueError:
            return {"status": "ok", "httpStatus": resp.status_code, "raw": text}
