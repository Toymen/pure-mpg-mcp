"""Organizational-unit search and navigation tools."""

from __future__ import annotations

import asyncio
from typing import Any

from ..context import _client, mcp


@mcp.tool()
async def search_organizations(name: str | None = None, size: int = 10, offset: int = 0) -> dict[str, Any]:
    """Search Max Planck organizational units (institutes, departments).

    Pass `name` to match on the unit name, or omit for a broad listing.
    Returns raw OU records (objectId, name, parent affiliations).
    """
    query: dict[str, Any] = (
        {"match": {"metadata.name": name}} if name else {"match_all": {}}
    )
    return await _client.search_ous(query=query, size=size, from_=offset)


@mcp.tool()
async def get_organization(ou_id: str) -> dict[str, Any]:
    """Get one Max Planck organizational unit by id (e.g. "ou_1234567")."""
    return await _client.get_ou(ou_id)


@mcp.tool()
async def list_top_organizations() -> dict[str, Any]:
    """List the top-level (root) Max Planck organizational units."""
    return await _client.ous_toplevel()


@mcp.tool()
async def list_first_level_organizations() -> dict[str, Any]:
    """List the first-level Max Planck organizational units (below the roots)."""
    return await _client.ous_firstlevel()


@mcp.tool()
async def organization_children(ou_id: str) -> Any:
    """List the direct child organizational units of an OU (e.g. departments of an institute)."""
    return await _client.ou_children(ou_id)


@mcp.tool()
async def organization_hierarchy(ou_id: str) -> dict[str, Any]:
    """Get the ancestor path of an OU, from itself up to the root institute.

    Useful to resolve which institute a department or sub-unit belongs to.
    Returns both the id path and the human-readable name path.
    """
    ids, names = await asyncio.gather(_client.ou_id_path(ou_id), _client.ou_name_path(ou_id))
    return {"ouId": ou_id, "idPath": ids, "namePath": names}
