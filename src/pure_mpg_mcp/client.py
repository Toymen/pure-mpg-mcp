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

# Elasticsearch rejects from+size beyond index.max_result_window (default 10k),
# and the PuRe scroll endpoint is server-capped, so offset pagination stops here.
MAX_RESULT_WINDOW = 10_000


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

    async def count_items(self, query: dict[str, Any]) -> int:
        """Count items matching a query without fetching any records (size=0)."""
        result = await self.search_items(query=query, size=0)
        return result.get("numberOfRecords", 0)

    async def fetch_all(
        self,
        query: dict[str, Any],
        max_records: int | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch records using rate-limited offset (from+size) pagination.

        The PuRe scroll endpoint is server-capped and the API exposes no
        stable unique sort field for search_after, so from+size is the only
        reliable strategy. A brief inter-page delay keeps request rates
        within polite limits.

        Pass ``max_records=None`` (default) to retrieve every matching record;
        pass a positive integer to cap the result. Retrieval is hard-capped at
        ``MAX_RESULT_WINDOW`` records because Elasticsearch rejects deeper
        offsets; callers see the true total via the search response.
        """
        import asyncio

        effective_size = min(page_size, max_records) if max_records is not None else page_size
        first = await self.search_items(query=query, size=effective_size, from_=0)
        records: list[dict[str, Any]] = list(first.get("records", []) or [])
        total = first.get("numberOfRecords", len(records))
        limit = max_records if max_records is not None else total
        target = min(limit, total, MAX_RESULT_WINDOW)

        while len(records) < target:
            await asyncio.sleep(0.05)
            page = await self.search_items(
                query=query,
                size=min(effective_size, target - len(records)),
                from_=len(records),
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

    async def export_search(
        self,
        query: dict[str, Any],
        format: str = "BibTex",
        citation: str | None = None,
        csl_cone_id: str | None = None,
        size: int = 100,
        from_: int = 0,
        sort: list[dict[str, Any]] | None = None,
    ) -> str:
        """POST /items/search?format=… — export a whole result set in one call.

        The search endpoint renders results directly as BibTex, EndNote,
        Marc_Xml, or formatted citations (escidoc_snippet/json_citation with
        ``citation``/``cslConeId``). Max 5000 items per download (API limit).
        """
        body: dict[str, Any] = {"query": query, "size": size, "from": from_}
        if sort:
            body["sort"] = sort
        resp = await self._post_json(
            "/items/search", body, format=format, citation=citation, cslConeId=csl_cone_id
        )
        return resp.text

    async def get_component_metadata(self, item_id: str, component_id: str) -> dict[str, Any]:
        """GET /items/{itemId}/component/{componentId}/metadata — file metadata."""
        resp = await self._get(f"/items/{item_id}/component/{component_id}/metadata")
        return resp.json()

    def component_content_url(self, item_id: str, component_id: str) -> str:
        """Direct download URL for a file component (anonymous for PUBLIC files)."""
        return f"{self.base_url}/items/{item_id}/component/{component_id}/content"

    def component_thumbnail_url(self, item_id: str, component_id: str) -> str:
        """Thumbnail URL for a file component (anonymous for PUBLIC files)."""
        return f"{self.base_url}/items/{item_id}/component/{component_id}/thumbnail"

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

    async def ous_firstlevel(self) -> dict[str, Any]:
        """GET /ous/firstlevel — first-level organizational units."""
        resp = await self._get("/ous/firstlevel")
        return resp.json()

    async def ou_children(self, ou_id: str) -> Any:
        """GET /ous/{ouId}/children — direct child organizational units."""
        resp = await self._get(f"/ous/{ou_id}/children")
        return resp.json()

    async def ou_id_path(self, ou_id: str) -> Any:
        """GET /ous/{ouId}/idPath — ancestor OU ids from the unit to the root."""
        resp = await self._get(f"/ous/{ou_id}/idPath")
        return self._json_or_text(resp)

    async def ou_name_path(self, ou_id: str) -> Any:
        """GET /ous/{ouId}/ouPath — ancestor OU names from the unit to the root."""
        resp = await self._get(f"/ous/{ou_id}/ouPath")
        return self._json_or_text(resp)

    @staticmethod
    def _json_or_text(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # --- contexts (collections) -------------------------------------------

    async def search_contexts(self, query: dict[str, Any], size: int = 10, from_: int = 0) -> dict[str, Any]:
        """POST /contexts/search — search contexts (collections)."""
        body = {"query": query, "size": size, "from": from_}
        resp = await self._post_json("/contexts/search", body)
        return resp.json()

    async def get_context(self, ctx_id: str) -> dict[str, Any]:
        """GET /contexts/{ctxId} — one context (collection)."""
        resp = await self._get(f"/contexts/{ctx_id}")
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

    async def feed_organization(self, ou_id: str) -> str:
        """GET /feed/organization/{ouId} — feed of recent releases for one OU."""
        resp = await self._get(f"/feed/organization/{ou_id}")
        return resp.text

    async def feed_search(self, q: str) -> str:
        """GET /feed/search — any search, rendered as an RSS/Atom feed."""
        resp = await self._get("/feed/search", q=q)
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
