"""MCP tool registration: importing this package registers every `@mcp.tool()`.

Re-exports every tool function so the whole surface is reachable from one
place (`from pure_mpg_mcp.tools import *`, or via `pure_mpg_mcp.server`).
"""

from __future__ import annotations

from .authors import analyze_authors, coauthorship_analysis
from .collections_feeds import (
    get_collection,
    open_access_feed,
    organization_feed,
    recent_publications,
    search_collections,
    search_feed,
    service_info,
)
from .enrichment import enrich_publication, get_citation_metrics
from .export import export_publication, export_search_results, get_file_metadata
from .fulltext import find_full_text
from .lookup import author_publications, find_by_doi, list_languages, resolve_author
from .organizations import (
    get_organization,
    list_first_level_organizations,
    list_top_organizations,
    organization_children,
    organization_hierarchy,
    search_organizations,
)
from .search import get_publication, search_publications, search_raw
from .stats import publication_statistics

__all__ = [
    "search_publications",
    "search_raw",
    "get_publication",
    "export_publication",
    "export_search_results",
    "get_file_metadata",
    "search_organizations",
    "get_organization",
    "list_top_organizations",
    "list_first_level_organizations",
    "organization_children",
    "organization_hierarchy",
    "search_collections",
    "get_collection",
    "recent_publications",
    "open_access_feed",
    "organization_feed",
    "search_feed",
    "service_info",
    "find_by_doi",
    "resolve_author",
    "list_languages",
    "author_publications",
    "publication_statistics",
    "coauthorship_analysis",
    "analyze_authors",
    "enrich_publication",
    "get_citation_metrics",
    "find_full_text",
]
