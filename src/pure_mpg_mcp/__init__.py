"""pure-mpg-mcp: an MCP server for the public PuRe (PubMan) REST API."""

from .client import PureClient

__version__ = "0.1.0"
__all__ = ["PureClient", "__version__"]
