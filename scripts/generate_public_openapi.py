"""Generate the anonymous public PuRe OpenAPI surface.

The official PubMan spec contains write, admin, login, import, and curation
operations. This file captures the endpoints that were verified or safely
classified from anonymous live probes, without advertising mutating APIs as
part of this MCP server's public read surface.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ponytail: makes `python scripts/generate_public_openapi.py` and pytest's
# load-by-path (see test_public_openapi.py) both resolve `scripts.openapi_ops`
# regardless of cwd; drop this if the script gains a proper console entry point.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.openapi_ops.feed_misc_ops import FEED_MISC_OPERATIONS
from scripts.openapi_ops.items_ops import ITEMS_OPERATIONS
from scripts.openapi_ops.ou_context_ops import OU_CONTEXT_OPERATIONS

OUT = Path("openapi/pure-public.openapi.json")

OPERATIONS = ITEMS_OPERATIONS + OU_CONTEXT_OPERATIONS + FEED_MISC_OPERATIONS


def build_openapi() -> dict[str, Any]:
    paths: dict[str, dict[str, Any]] = {}
    for path, method, op in OPERATIONS:
        paths.setdefault(path, {})[method] = op
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "PuRe PubMan Anonymous Public REST API",
            "version": "live-probed-2026-07-07",
            "description": (
                "Derived from anonymous live probing of https://pure.mpg.de/rest. "
                "This intentionally excludes write, curation, import, password, and admin operations."
            ),
        },
        "servers": [{"url": "https://pure.mpg.de/rest"}],
        "security": [],
        "x-liveDiscovery": {
            "method": "safe anonymous try/error probing plus MCP regression live tests",
            "rateLimit": (
                "The service returned HTTP 429 during broad mixed-endpoint probing; 429 responses were HTML and "
                "did not include Retry-After or X-RateLimit headers. Follow-up probes on /items/search succeeded "
                "with 8 requests at 1.0s spacing, 8 requests at 0.25s spacing, and 20 requests at 0.1s spacing. "
                "The broad-probe block cleared within roughly 10 minutes. Prefer low concurrency and avoid sweeping "
                "admin/import/mutating paths."
            ),
            "largeResultWindow": (
                "Anonymous /items/search reported 593751 records during probing. Offset pagination returned records "
                "at offsets 500000, 590000, and 593750; offsets equal to or beyond the total returned zero records. "
                "Page sizes up to 25000 were observed working, while 26000 and higher returned HTTP 500, so the MCP "
                "client caps bulk pages at 20000 and defaults fetch_all to 10000."
            ),
            "excluded": [
                "PUT/DELETE operations were not executed because they are mutating.",
                "POST create/import/login/password/admin operations are excluded from the read-only public surface.",
                "Endpoints returning 401/403 for anonymous users are not advertised as public operations.",
            ],
        },
        "paths": paths,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build_openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
