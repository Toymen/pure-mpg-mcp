"""Small, polite live probe for PuRe public rate-limit behavior.

Default mode uses /items/search with size=0 and stops on the first non-2xx
response. It is intentionally conservative; use larger counts or lower
intervals only when you are deliberately investigating limits.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import Counter

import httpx


BASE_URL = "https://pure.mpg.de/rest"
BODY = {"query": {"match_all": {}}, "size": 0, "from": 0}


async def probe(count: int, interval: float, base_url: str) -> list[int]:
    statuses: list[int] = []
    started = time.monotonic()
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=False,
        headers={"User-Agent": "pure-mpg-mcp-limit-probe/0.1", "Accept": "application/json"},
    ) as client:
        for idx in range(count):
            t0 = time.monotonic()
            response = await client.post(f"{base_url.rstrip('/')}/items/search", json=BODY)
            elapsed = time.monotonic() - t0
            statuses.append(response.status_code)
            headers = _interesting_headers(response.headers)
            print(
                idx + 1,
                response.status_code,
                f"t+{time.monotonic() - started:.2f}s",
                f"{elapsed:.3f}s",
                headers,
                response.text[:80].replace("\n", " "),
            )
            if response.status_code == 429:
                break
            await asyncio.sleep(interval)
    print("summary", dict(Counter(statuses)))
    return statuses


def _interesting_headers(headers: httpx.Headers) -> dict[str, str]:
    names = {"retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "server", "date"}
    return {key: value for key, value in headers.items() if key.lower() in names}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=8, help="maximum requests to send")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds to sleep between requests")
    parser.add_argument("--base-url", default=BASE_URL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(probe(args.count, args.interval, args.base_url))


if __name__ == "__main__":
    main()
