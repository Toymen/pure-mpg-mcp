"""MCP server exposing the public read surface of the PuRe (PubMan) REST API.

PuRe is the Max Planck Society's publication repository (https://pure.mpg.de).
This server is anonymous and read-only: it can search and retrieve RELEASED,
publicly visible publication records, organizational units, collections, and
feeds. It cannot log in, write, or access embargoed/private content.

Run:
    pure-mpg-mcp                       # stdio transport (default; local clients)
    MCP_TRANSPORT=http pure-mpg-mcp    # streamable-HTTP at http://0.0.0.0:$PORT/mcp
                                       # (for hosting a remote connector URL)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .context import _client, _cone, _datasets, _enrich, mcp  # noqa: F401 — re-exported for tests
from .stats_helpers import _language_codes  # noqa: F401 — re-exported for tests
from .tools import *  # noqa: F401,F403 — registers every @mcp.tool() and re-exports it
from .vocab import _GENRES, _LANGUAGES  # noqa: F401 — re-exported for tests

if TYPE_CHECKING:
    from mcp.server.transport_security import TransportSecuritySettings


def main() -> None:
    """Console-script entry point.

    Defaults to stdio (for local clients like Claude Desktop/Code). Set
    ``MCP_TRANSPORT=http`` (or ``streamable-http``) to serve over Streamable
    HTTP instead — used when hosting a remote connector URL. ``HOST``/``PORT``
    configure the bind address (``PORT`` is provided by most hosting platforms).
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.settings.host = os.getenv("HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("PORT", "8000"))
        mcp.settings.transport_security = _transport_security()
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


def _transport_security() -> "TransportSecuritySettings":
    """Configure the Host/Origin allow-list for HTTP transport.

    The MCP SDK enables DNS-rebinding protection by default, trusting only
    localhost — which rejects a deployed hostname with HTTP 421. We trust the
    platform-provided external hostname (Render sets ``RENDER_EXTERNAL_HOSTNAME``)
    plus anything in ``MCP_ALLOWED_HOSTS`` (comma-separated). If no host can be
    determined, protection is disabled — safe here because the server is public
    and read-only with no auth or local resources to protect.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    hosts = [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    platform_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if platform_host:
        hosts.append(platform_host)
    if not hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    # accept each host with and without an explicit port
    allowed_hosts = ["localhost:*", "127.0.0.1:*"]
    allowed_origins: list[str] = []
    for h in hosts:
        allowed_hosts += [h, f"{h}:*"]
        allowed_origins += [f"https://{h}", f"http://{h}"]
    return TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


if __name__ == "__main__":
    main()
