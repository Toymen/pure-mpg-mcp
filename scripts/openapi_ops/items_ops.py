"""OpenAPI operations for the /items/* surface (search, retrieval, export, files)."""

from __future__ import annotations

from .common import ANY, SEARCH_BODY, TEXT, operation

ITEMS_OPERATIONS = [
    operation("Search public publication items", method="POST", path="/items/search", request_body=SEARCH_BODY, status=200),
    operation(
        "Continue a public item search scroll",
        method="GET",
        path="/items/search/scroll",
        parameters=["scrollId"],
        status=200,
        limitation="Requires a valid scrollId returned by /items/search; invalid ids returned HTTP 500 in live probing.",
    ),
    operation("Get one public publication item", method="GET", path="/items/{itemId}", parameters=["itemId"], status=200),
    operation("Get public item history", method="GET", path="/items/{itemId}/history", parameters=["itemId"], status=200),
    operation(
        "Export one public item",
        method="GET",
        path="/items/{itemId}/export",
        parameters=["itemId", "format"],
        status=200,
        response_media=TEXT,
    ),
    operation(
        "Get anonymous authorization flags for one item",
        method="GET",
        path="/items/{itemId}/authorization",
        parameters=["itemId"],
        status=200,
    ),
    operation(
        "Get public file component metadata",
        method="GET",
        path="/items/{itemId}/component/{componentId}/metadata",
        parameters=["fileItemId", "componentId"],
        accept=TEXT,
        status=200,
        response_media=TEXT,
        limitation="Live service returns text/plain; application/json returns HTTP 406.",
    ),
    operation(
        "Download public file component content",
        method="GET",
        path="/items/{itemId}/component/{componentId}/content",
        parameters=["fileItemId", "componentId"],
        accept=ANY,
        status=200,
        response_media="application/octet-stream",
        limitation="Only public file components are anonymously downloadable.",
    ),
    operation(
        "Get public file component thumbnail",
        method="GET",
        path="/items/{itemId}/component/{componentId}/thumbnail",
        parameters=["fileItemId", "componentId"],
        accept=ANY,
        status=200,
        response_media="image/*",
        limitation="Only components with generated thumbnails return image data.",
    ),
]
