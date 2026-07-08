"""Context (collection), feed, and service-info endpoints."""

from __future__ import annotations

from typing import Any

from .base import BaseClient

FEED_ACCEPT = "application/atom+xml, application/rss+xml, application/xml, text/xml, */*"


class ContextsFeedsMixin(BaseClient):
    async def search_contexts(self, query: dict[str, Any], size: int = 10, from_: int = 0) -> dict[str, Any]:
        """POST /contexts/search — search contexts (collections)."""
        body = {"query": query, "size": size, "from": from_}
        resp = await self._post_json("/contexts/search", body)
        return resp.json()

    async def get_context(self, ctx_id: str) -> dict[str, Any]:
        """GET /contexts/{ctxId} — one context (collection)."""
        resp = await self._get(f"/contexts/{ctx_id}")
        return resp.json()

    async def feed_recent(self) -> str:
        """GET /feed/recent — RSS/Atom feed of recently released items."""
        resp = await self._get("/feed/recent", accept=FEED_ACCEPT)
        return resp.text

    async def feed_open_access(self) -> str:
        """GET /feed/oa — feed of recent open-access items."""
        resp = await self._get("/feed/oa", accept=FEED_ACCEPT)
        return resp.text

    async def feed_organization(self, ou_id: str) -> str:
        """GET /feed/organization/{ouId} — feed of recent releases for one OU."""
        resp = await self._get(f"/feed/organization/{ou_id}", accept=FEED_ACCEPT)
        return resp.text

    async def feed_search(self, q: str) -> str:
        """GET /feed/search — any search, rendered as an RSS/Atom feed."""
        resp = await self._get("/feed/search", accept=FEED_ACCEPT, q=q)
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
