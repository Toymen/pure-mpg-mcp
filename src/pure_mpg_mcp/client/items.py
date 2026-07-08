"""Item search, retrieval, export, and file-component endpoints."""

from __future__ import annotations

from typing import Any

from .base import BaseClient


class ItemsMixin(BaseClient):
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
        resp = await self._get(f"/items/{item_id}/component/{component_id}/metadata", accept="text/plain")
        try:
            return resp.json()
        except ValueError:
            return self._parse_text_metadata(resp.text)

    def component_content_url(self, item_id: str, component_id: str) -> str:
        """Direct download URL for a file component (anonymous for PUBLIC files)."""
        return f"{self.base_url}/items/{item_id}/component/{component_id}/content"

    def component_thumbnail_url(self, item_id: str, component_id: str) -> str:
        """Thumbnail URL for a file component (anonymous for PUBLIC files)."""
        return f"{self.base_url}/items/{item_id}/component/{component_id}/thumbnail"

    @staticmethod
    def _parse_text_metadata(text: str) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(": ", 1) if ": " in line else line.split(":", 1)
            key = key.strip()
            if key:
                meta[key] = value.strip()
        return meta or {"raw": text}
