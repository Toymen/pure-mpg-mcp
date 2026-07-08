"""Organizational unit (institute/department) endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from .base import BaseClient


class OusMixin(BaseClient):
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
        resp = await self._get(f"/ous/{ou_id}/idPath", accept="text/plain")
        return self._json_or_text_list(resp)

    async def ou_name_path(self, ou_id: str) -> Any:
        """GET /ous/{ouId}/ouPath — ancestor OU names from the unit to the root."""
        resp = await self._get(f"/ous/{ou_id}/ouPath", accept="text/plain")
        return self._json_or_text_list(resp)

    @staticmethod
    def _json_or_text_list(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            text = resp.text.strip()
            if "," in text:
                return [part.strip() for part in text.split(",") if part.strip()]
            return text
