"""Bibliometric distribution tool (client-side aggregation over PuRe records)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from .. import analysis
from ..context import _client, mcp
from ..search_query import _date_clause
from ..stats_helpers import _count_subquery, _gather_counts, _language_codes, _term_distribution
from ..vocab import _DATE_PUBLISHED, _GENRES, _OA_STATUSES


@mcp.tool()
async def publication_statistics(
    query: dict[str, Any] | None = None,
    group_by: str = "year",
    max_records: int | None = None,
    top: int = 20,
) -> dict[str, Any]:
    """Compute distributions over a set of publications.

    `group_by` is one of: "year", "genre", "language", "open_access",
    "oa_status" (GOLD/GREEN/HYBRID/MISCELLANEOUS/NOT_SPECIFIED/CLOSED_ACCESS),
    "organization". `query` is an Elasticsearch query DSL object (default: all
    records).

    For "year" (bracketed across print and online publication dates), "genre",
    "language" (codes sourced live from the CONE authority; see `list_languages`),
    "open_access", and "oa_status" the counts are derived from concurrent count
    sub-queries (size=0) — no records are fetched, so results are exact
    regardless of dataset size. For "organization", records are fetched (all
    by default; cap with `max_records`) and every creator role counts, not
    just authors/editors.
    """
    q = query or {"match_all": {}}

    if group_by == "year":
        # A publication's year may only be recorded online (preprints, recent
        # articles ahead of print) — bracket the range across both date fields.
        bounds = await asyncio.gather(
            *[
                _client.search_items(
                    query={"bool": {"must": [q], "filter": [{"exists": {"field": f}}]}},
                    size=1, sort=[{f: {"order": order}}],
                )
                for f in _DATE_PUBLISHED
                for order in ("asc", "desc")
            ]
        )

        def _yr(resp: dict[str, Any], field: str) -> int | None:
            recs = resp.get("records") or []
            if not recs:
                return None
            val = str(((recs[0].get("data") or recs[0]).get("metadata") or {}).get(field) or "")
            return int(val[:4]) if len(val) >= 4 and val[:4].isdigit() else None

        years = [
            y
            for resp, field in zip(bounds, [f for f in _DATE_PUBLISHED for _ in (0, 1)])
            if (y := _yr(resp, field)) is not None
        ]
        min_year = max(min(years, default=1900), 1800)
        max_year = max(years, default=datetime.now().year)
        year_clauses = [
            (str(yr), _date_clause(_DATE_PUBLISHED, str(yr), str(yr)))
            for yr in range(min_year, max_year + 1)
        ]
        raw = await _gather_counts(q, year_clauses)
        buckets = sorted([{"key": k, "count": v} for k, v in raw if v > 0], key=lambda b: b["key"])
        return {
            "groupBy": group_by,
            "totalMatchingRecords": sum(b["count"] for b in buckets),
            "buckets": buckets[:top] if len(buckets) > top else buckets,
            "note": "exact counts via targeted sub-queries",
        }

    elif group_by == "genre":
        return await _term_distribution(q, group_by, "metadata.genre", _GENRES, top)

    elif group_by == "language":
        return await _term_distribution(q, group_by, "metadata.languages", await _language_codes(), top)

    elif group_by == "open_access":
        # A public file whose oaStatus is explicitly CLOSED_ACCESS is a locator
        # pointing at a paywalled page, not an open-access copy.
        oa_filter = {
            "bool": {
                "must": [{"term": {"files.visibility": "PUBLIC"}}],
                "must_not": [{"term": {"files.oaStatus": "CLOSED_ACCESS"}}],
            }
        }
        total, oa = await asyncio.gather(
            _client.count_items(q),
            _count_subquery(q, oa_filter),
        )
        return {
            "groupBy": group_by,
            "totalMatchingRecords": total,
            "buckets": [
                {"key": "open_access", "count": oa},
                {"key": "closed", "count": max(0, total - oa)},
            ],
            "note": "exact counts via targeted sub-queries",
        }

    elif group_by == "oa_status":
        return await _term_distribution(q, group_by, "files.oaStatus", _OA_STATUSES, top)

    else:  # organization — requires fetching records to inspect affiliation names
        records = await _client.fetch_all(q, max_records=max_records)
        result = analysis.distribution(records, group_by=group_by, top=top)
        result["note"] = f"aggregated from {len(records)} fetched records"
        return result
