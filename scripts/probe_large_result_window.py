"""Probe PuRe's large result-window behavior without downloading everything.

This checks the cases that matter for future 500k+ MCP requests:
- total result count
- largest safe page size observed by anonymous probing
- offsets near and beyond the end of the result set

It deliberately fetches only a few pages/records; it is a boundary probe, not a
bulk downloader.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass

import httpx


BASE_URL = "https://pure.mpg.de/rest"
SAFE_PAGE_SIZE = 20_000
KNOWN_FAILING_PAGE_SIZE = 26_000


@dataclass
class ProbeResult:
    name: str
    status: int
    elapsed: float
    total: int | None
    records: int
    first_item_id: str | None


async def search(client: httpx.AsyncClient, *, size: int, offset: int) -> ProbeResult:
    started = time.monotonic()
    response = await client.post(
        "/items/search",
        json={"query": {"match_all": {}}, "size": size, "from": offset},
    )
    elapsed = time.monotonic() - started
    total = None
    records = 0
    first_item_id = None
    try:
        data = response.json()
        total = data.get("numberOfRecords")
        result_records = data.get("records") or []
        records = len(result_records)
        if result_records:
            first = result_records[0].get("data", result_records[0])
            first_item_id = first.get("objectId")
    except ValueError:
        pass
    return ProbeResult(f"size={size},offset={offset}", response.status_code, elapsed, total, records, first_item_id)


async def probe(base_url: str = BASE_URL, pause: float = 1.0) -> list[ProbeResult]:
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=120,
        follow_redirects=False,
        headers={"Accept": "application/json", "User-Agent": "pure-mpg-mcp-large-window-probe/0.1"},
    ) as client:
        first = await search(client, size=0, offset=0)
        total = first.total or 0
        offsets = [0, min(500_000, max(total - 1, 0)), max(total - 1, 0), total, total + 1]
        cases = [(SAFE_PAGE_SIZE, 0), (KNOWN_FAILING_PAGE_SIZE, 0), *[(1, offset) for offset in offsets]]
        results = [first]
        for size, offset in cases:
            await asyncio.sleep(pause)
            results.append(await search(client, size=size, offset=offset))
        return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--pause", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = asyncio.run(probe(base_url=args.base_url, pause=args.pause))
    for result in results:
        print(
            result.name,
            "status",
            result.status,
            "time",
            f"{result.elapsed:.2f}s",
            "total",
            result.total,
            "records",
            result.records,
            "first",
            result.first_item_id,
        )


if __name__ == "__main__":
    main()
