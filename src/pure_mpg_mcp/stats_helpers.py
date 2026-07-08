"""Concurrent count-based aggregation helpers used by `publication_statistics`."""

from __future__ import annotations

import asyncio
from typing import Any

from .context import _client, _cone
from .vocab import _LANGUAGES

_STATS_CONCURRENCY = 8  # max parallel count requests


async def _count_subquery(base: dict[str, Any], filter_clause: dict[str, Any]) -> int:
    q: dict[str, Any] = {"bool": {"must": [base], "filter": [filter_clause]}}
    return await _client.count_items(q)


async def _gather_counts(
    base: dict[str, Any],
    items: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, int]]:
    sem = asyncio.Semaphore(_STATS_CONCURRENCY)

    async def _one(key: str, clause: dict[str, Any]) -> tuple[str, int]:
        async with sem:
            return key, await _count_subquery(base, clause)

    return list(await asyncio.gather(*[_one(k, c) for k, c in items]))


async def _term_distribution(
    q: dict[str, Any], group_by: str, field: str, values: list[str], top: int
) -> dict[str, Any]:
    """Exact per-value counts for a term field, via concurrent count sub-queries."""
    raw = await _gather_counts(q, [(v, {"term": {field: v}}) for v in values])
    buckets = sorted([{"key": k, "count": v} for k, v in raw if v > 0], key=lambda b: -b["count"])
    return {
        "groupBy": group_by,
        "totalMatchingRecords": sum(b["count"] for b in buckets),
        "buckets": buckets[:top],
        "note": "exact counts via targeted sub-queries",
    }


async def _language_codes() -> list[str]:
    """ISO 639-3 codes to check for `publication_statistics(group_by="language")`.

    Sourced live from the CONE authority vocabulary — the authoritative list
    of languages PubMan actually accepts, so it can't drift out of date the
    way a hand-maintained list can. Falls back to the static `_LANGUAGES`
    list if CONE (a separate service from the main REST API) is unreachable.
    """
    try:
        entries = await _cone.languages()
        codes = sorted({e["id"] for e in entries if e.get("id")})
        if codes:
            return codes
    except Exception:  # noqa: BLE001 — CONE is best-effort here; the static list is the fallback
        pass
    return _LANGUAGES
