"""Client for the public CONE authority service (persons, journals, etc.).

CONE backs PuRe's controlled vocabularies. The persons authority is the most
useful here: it maps a person id (e.g. ``persons314810``) to a *full* given
name, family name, affiliation, and — when known — an ORCID. Publication
records frequently store only initials (``"J."``), so resolving against CONE
is what makes downstream author analysis (full names, ORCID, affiliation) viable.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

DEFAULT_CONE_URL = "https://pure.mpg.de/cone"
_ORCID_RE = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dxX]\b")
# CONE returns mangled URI-as-key JSON; we match on key *suffixes*.
_GIVEN_KEYS = ("givenname",)
_FAMILY_KEYS = ("family_name",)


class ConeClient:
    """Minimal async wrapper over the public CONE authority API."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or os.getenv("PURE_CONE_URL") or DEFAULT_CONE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": "pure-mpg-mcp/0.1", "Accept": "application/json"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "ConeClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    @staticmethod
    def _normalize_id(person_id: str) -> str:
        """Accept bare ids, CONE paths, or full URLs and return the bare id."""
        return person_id.rstrip("/").split("/")[-1]

    async def query_persons(self, name: str, limit: int = 10) -> list[dict[str, str]]:
        """Autocomplete-style search; returns [{id, type, value}, ...].

        ``type`` is "main" for the canonical label and "alt" for variants.
        """
        resp = await self._client.get(
            "/persons/query", params={"q": name, "format": "json", "n": limit}
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return []

    async def resolve_person(self, person_id: str) -> dict[str, Any]:
        """Resolve a person id to a clean record: full names, affiliation, ORCID."""
        pid = self._normalize_id(person_id)
        resp = await self._client.get(
            f"/persons/resource/{pid}", params={"format": "json"}
        )
        resp.raise_for_status()
        raw = resp.json()
        return self._clean_person(pid, raw)

    async def languages(self) -> list[dict[str, str]]:
        """The full ISO 639-3 language vocabulary CONE serves, as [{id, value}, ...].

        The authoritative source for `metadata.languages` values — covers
        every language PubMan accepts, unlike any list maintained by hand.
        """
        resp = await self._client.get("/iso639-3/all", params={"format": "json"})
        resp.raise_for_status()
        try:
            raw = resp.json()
        except ValueError:
            return []
        return [self._clean_language(entry) for entry in raw if isinstance(entry, dict)]

    @staticmethod
    def _clean_language(entry: dict[str, Any]) -> dict[str, str]:
        out = {k: str(v) for k, v in entry.items() if v is not None}
        if "id" in out:
            out["id"] = out["id"].rstrip("/").split("/")[-1]
        return out

    @staticmethod
    def _clean_person(pid: str, raw: dict[str, Any]) -> dict[str, Any]:
        given = family = title = affiliation = orcid = None
        for k, v in raw.items():
            kl = k.lower()
            if isinstance(v, str):
                if any(kl.endswith(s) for s in _GIVEN_KEYS):
                    given = v
                elif any(kl.endswith(s) for s in _FAMILY_KEYS):
                    family = v
                elif kl.endswith("title") and family is None:
                    title = v
                elif orcid is None and _ORCID_RE.search(v):
                    orcid = _ORCID_RE.search(v).group(0)
            elif isinstance(v, dict):
                # affiliation lives in a nested "position" object
                for vv in v.values():
                    if isinstance(vv, str) and "Society" in vv or (isinstance(vv, str) and len(vv) > 20):
                        affiliation = affiliation or vv
                    if isinstance(vv, str) and orcid is None and _ORCID_RE.search(vv):
                        orcid = _ORCID_RE.search(vv).group(0)
        return {
            "personId": pid,
            "givenName": given,
            "familyName": family,
            "label": title,
            "affiliation": affiliation,
            "orcid": orcid,
        }
