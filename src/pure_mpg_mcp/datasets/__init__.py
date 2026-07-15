"""Research-data discovery: does a DOI or ORCID have datasets behind it?

Complements `enrichment` (which attaches scholarly signals to a PuRe record):
these connectors ask the dataset registries and link services whether research
data exist for a publication DOI or a researcher ORCID. All sources are free
and unauthenticated; capabilities and verified example queries live in
docs/research-data-discovery.md.

Contract per provider: a list of normalized hits ({doi, title, publisher,
year, relation}); an empty list means "queried fine, nothing found" (a
meaningful answer here), None means the provider was unreachable and is
omitted from the result.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..enrichment import _polite_email, normalize_doi
from . import doi_sources as _doi
from . import orcid_sources as _orcid

DOI_SOURCES = ("scholexplorer", "datacite", "b2find", "crossref", "zenodo", "figshare", "dryad")
ORCID_SOURCES = ("datacite", "openaire", "openalex", "zenodo", "figshare")

_ORCID_RE = re.compile(r"\b(\d{4}-\d{4}-\d{4}-\d{3}[\dxX])\b")


def normalize_orcid(orcid: str) -> str | None:
    """Bare ORCID id from bare/URL forms, or None if none is found."""
    m = _ORCID_RE.search(orcid)
    return m.group(1) if m else None


class Datasets:
    """Async connectors over the public dataset registries (one shared client)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": f"pure-mpg-mcp ({_polite_email()})", "Accept": "application/json"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- DOI-keyed providers ----------------------------------------------

    async def scholexplorer(self, doi: str) -> list[dict[str, Any]] | None:
        return await _doi.scholexplorer(self._client, normalize_doi(doi))

    async def datacite_by_doi(self, doi: str) -> list[dict[str, Any]] | None:
        return await _doi.datacite(self._client, normalize_doi(doi))

    async def b2find(self, doi: str) -> list[dict[str, Any]] | None:
        return await _doi.b2find(self._client, normalize_doi(doi))

    async def crossref_supplements(self, doi: str) -> list[dict[str, Any]] | None:
        return await _doi.crossref(self._client, normalize_doi(doi), _polite_email())

    async def zenodo_by_doi(self, doi: str) -> list[dict[str, Any]] | None:
        return await _doi.zenodo(self._client, normalize_doi(doi))

    async def figshare_by_doi(self, doi: str) -> list[dict[str, Any]] | None:
        return await _doi.figshare(self._client, normalize_doi(doi))

    async def dryad(self, doi: str) -> list[dict[str, Any]] | None:
        return await _doi.dryad(self._client, normalize_doi(doi))

    # --- ORCID-keyed providers --------------------------------------------

    async def datacite_by_orcid(self, orcid: str) -> list[dict[str, Any]] | None:
        return await _orcid.datacite(self._client, orcid)

    async def openaire_by_orcid(self, orcid: str) -> list[dict[str, Any]] | None:
        return await _orcid.openaire(self._client, orcid)

    async def openalex_by_orcid(self, orcid: str) -> list[dict[str, Any]] | None:
        return await _orcid.openalex(self._client, orcid, _polite_email())

    async def zenodo_by_orcid(self, orcid: str) -> list[dict[str, Any]] | None:
        return await _orcid.zenodo(self._client, orcid)

    async def figshare_by_orcid(self, orcid: str) -> list[dict[str, Any]] | None:
        return await _orcid.figshare(self._client, orcid)

    # --- fan-out ------------------------------------------------------------

    async def by_doi(self, doi: str, sources: list[str]) -> dict[str, list[dict[str, Any]]]:
        fns = {
            "scholexplorer": self.scholexplorer,
            "datacite": self.datacite_by_doi,
            "b2find": self.b2find,
            "crossref": self.crossref_supplements,
            "zenodo": self.zenodo_by_doi,
            "figshare": self.figshare_by_doi,
            "dryad": self.dryad,
        }
        return await self._fetch(doi, sources, fns)

    async def by_orcid(self, orcid: str, sources: list[str]) -> dict[str, list[dict[str, Any]]]:
        fns = {
            "datacite": self.datacite_by_orcid,
            "openaire": self.openaire_by_orcid,
            "openalex": self.openalex_by_orcid,
            "zenodo": self.zenodo_by_orcid,
            "figshare": self.figshare_by_orcid,
        }
        return await self._fetch(orcid, sources, fns)

    @staticmethod
    async def _fetch(key: str, sources: list[str], fns: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for src in sources:
            fn = fns.get(src)
            if fn is None:
                continue
            result = await fn(key)
            if result is not None:
                out[src] = result
        return out
