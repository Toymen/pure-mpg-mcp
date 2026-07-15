"""Shared app singletons: the FastMCP instance and the three backing clients.

Tool modules import these directly; tests patch methods on `_client`/`_cone`/
`_enrich` (the same instances everywhere, regardless of which module imports
them) rather than replacing the names themselves.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import PureClient
from .cone import ConeClient
from .datasets import Datasets
from .enrichment import Enrichment

mcp = FastMCP("pure-mpg")
_client = PureClient()
_cone = ConeClient()
_enrich = Enrichment()
_datasets = Datasets()


@mcp.custom_route("/health", methods=["GET", "HEAD"])
async def _health(_request: Any) -> Any:
    """Plain HTTP health check for the hosting platform (the MCP endpoint itself expects the MCP protocol, not a bare GET)."""
    from starlette.responses import PlainTextResponse

    return PlainTextResponse("ok")
