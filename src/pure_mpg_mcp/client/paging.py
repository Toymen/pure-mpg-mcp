"""Bulk record traversal via offset pagination."""

from __future__ import annotations

import asyncio
from typing import Any

from .base import BaseClient

MAX_SAFE_SEARCH_PAGE_SIZE = 20_000
DEFAULT_FETCH_ALL_PAGE_SIZE = 10_000


class PagingMixin(BaseClient):
    async def fetch_all(
        self,
        query: dict[str, Any],
        max_records: int | None = None,
        page_size: int = DEFAULT_FETCH_ALL_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Fetch all matching records into a list.

        For very large result sets prefer `fetch_pages()`, which yields one
        page at a time and avoids holding 500k+ records in memory.
        """
        records: list[dict[str, Any]] = []
        async for page in self.fetch_pages(query=query, max_records=max_records, page_size=page_size):
            records.extend(page)
        return records[:max_records] if max_records is not None else records

    async def fetch_pages(
        self,
        query: dict[str, Any],
        max_records: int | None = None,
        page_size: int = DEFAULT_FETCH_ALL_PAGE_SIZE,
        page_delay: float = 0.05,
    ):
        """Yield matching records page by page using offset pagination.

        Two alternatives were tried and rejected: the PuRe scroll endpoint
        (``/items/search/scroll``) is server-side capped at roughly 1000
        records regardless of the true match count, and ``search_after``
        keyset pagination has no valid stable sort field on this deployment
        (``objectId.keyword`` is not indexed). Plain from+size offset
        pagination has been verified live well past 500k records, so it is
        used despite Elasticsearch's textbook ``max_result_window`` default —
        this PuRe instance is evidently configured with a much higher limit.
        A brief inter-page delay keeps request rates within polite limits.

        Pass ``max_records=None`` (default) to traverse every matching record;
        pass a positive integer to cap the traversal. Pages are capped at the
        live-safe size of 20,000 records and item-search calls retry 429/5xx
        responses with bounded exponential backoff.
        """
        effective_size = min(page_size, MAX_SAFE_SEARCH_PAGE_SIZE)
        if max_records is not None:
            effective_size = min(effective_size, max_records)
        if effective_size <= 0:
            return

        first = await self.search_items(query=query, size=effective_size, from_=0)
        batch: list[dict[str, Any]] = list(first.get("records", []) or [])
        total = first.get("numberOfRecords", len(batch))
        limit = max_records if max_records is not None else total
        target = min(limit, total)
        yielded = 0

        if batch:
            chunk = batch[:target]
            yielded += len(chunk)
            yield chunk

        while yielded < target:
            await asyncio.sleep(page_delay)
            page = await self.search_items(
                query=query,
                size=min(effective_size, target - yielded),
                from_=yielded,
            )
            batch = page.get("records", []) or []
            if not batch:
                break
            yielded += len(batch)
            yield batch
