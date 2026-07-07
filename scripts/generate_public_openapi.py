"""Generate the anonymous public PuRe OpenAPI surface.

The official PubMan spec contains write, admin, login, import, and curation
operations. This file captures the endpoints that were verified or safely
classified from anonymous live probes, without advertising mutating APIs as
part of this MCP server's public read surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


OUT = Path("openapi/pure-public.openapi.json")

JSON = "application/json"
TEXT = "text/plain"
ATOM = "application/atom+xml, application/rss+xml, application/xml, text/xml, */*"
ANY = "*/*"

COMMON_PARAMETERS: dict[str, dict[str, Any]] = {
    "itemId": {"name": "itemId", "in": "path", "required": True, "schema": {"type": "string"}, "example": "item_1552993"},
    "fileItemId": {"name": "itemId", "in": "path", "required": True, "schema": {"type": "string"}, "example": "item_1554385"},
    "componentId": {
        "name": "componentId",
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
        "example": "file_2123384",
    },
    "ouId": {"name": "ouId", "in": "path", "required": True, "schema": {"type": "string"}, "example": "ou_1497640"},
    "ctxId": {"name": "ctxId", "in": "path", "required": True, "schema": {"type": "string"}, "example": "ctx_1835112"},
    "sitemapFile": {
        "name": "sitemapFile",
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
        "example": "sitemap.xml",
    },
    "size": {"name": "size", "in": "query", "schema": {"type": "integer", "default": 10, "minimum": 0}},
    "from": {"name": "from", "in": "query", "schema": {"type": "integer", "default": 0, "minimum": 0}},
    "format": {"name": "format", "in": "query", "schema": {"type": "string"}, "example": "BibTex"},
    "scrollId": {"name": "scrollId", "in": "query", "required": True, "schema": {"type": "string"}},
    "q": {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}, "example": "graphene"},
}


def response(description: str, media_type: str = JSON) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            media_type: {
                "schema": {
                    "type": "string" if media_type != JSON else "object",
                    "additionalProperties": True,
                }
            }
        },
    }


SEARCH_BODY = {
    "required": True,
    "content": {
        JSON: {
            "schema": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "object", "additionalProperties": True},
                    "size": {"type": "integer", "default": 10, "minimum": 0},
                    "from": {"type": "integer", "default": 0, "minimum": 0},
                    "sort": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                },
            },
            "example": {"query": {"match_all": {}}, "size": 1, "from": 0},
        }
    },
}


def operation(
    summary: str,
    *,
    method: str,
    path: str,
    parameters: list[str] | None = None,
    request_body: dict[str, Any] | None = None,
    accept: str = JSON,
    status: int,
    public: bool = True,
    limitation: str | None = None,
    response_media: str = JSON,
) -> tuple[str, str, dict[str, Any]]:
    op: dict[str, Any] = {
        "summary": summary,
        "operationId": (
            method.lower()
            + "_"
            + path.strip("/").replace("/", "_").replace("{", "").replace("}", "").replace("-", "_")
        ),
        "parameters": [COMMON_PARAMETERS[name] for name in parameters or []],
        "responses": {
            str(status): response("Observed anonymous live response", response_media),
            "401": response("Authentication required or permission denied"),
            "429": response("Rate limited by the public PuRe service", "text/html"),
        },
        "x-liveProbe": {
            "anonymous": True,
            "confirmedPublic": public,
            "observedStatus": status,
            "accept": accept,
            "source": "anonymous live probes and regression live tests on 2026-07-07",
        },
    }
    if request_body:
        op["requestBody"] = request_body
    if limitation:
        op["x-liveProbe"]["limitation"] = limitation
    return path, method.lower(), op


OPERATIONS = [
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
    operation("Search public organizational units", method="POST", path="/ous/search", request_body=SEARCH_BODY, status=200),
    operation("Get one public organizational unit", method="GET", path="/ous/{ouId}", parameters=["ouId"], status=200),
    operation("Get OU parents", method="GET", path="/ous/{ouId}/parents", parameters=["ouId"], status=200),
    operation("Get OU children", method="GET", path="/ous/{ouId}/children", parameters=["ouId"], status=200),
    operation(
        "Get OU id path",
        method="GET",
        path="/ous/{ouId}/idPath",
        parameters=["ouId"],
        accept=TEXT,
        status=200,
        response_media=TEXT,
        limitation="Live service returns text/plain comma-separated ids; application/json returns HTTP 406.",
    ),
    operation(
        "Get OU name path",
        method="GET",
        path="/ous/{ouId}/ouPath",
        parameters=["ouId"],
        accept=TEXT,
        status=200,
        response_media=TEXT,
        limitation="Live service returns text/plain comma-separated names; application/json returns HTTP 406.",
    ),
    operation("List root OUs", method="GET", path="/ous/toplevel", status=200),
    operation("List first-level OUs", method="GET", path="/ous/firstlevel", status=200),
    operation("Search public contexts", method="POST", path="/contexts/search", request_body=SEARCH_BODY, status=200),
    operation("Get one public context", method="GET", path="/contexts/{ctxId}", parameters=["ctxId"], status=200),
    operation(
        "Recent-publications Atom feed",
        method="GET",
        path="/feed/recent",
        accept=ATOM,
        status=200,
        response_media="application/atom+xml",
        limitation="application/json Accept returns HTTP 406.",
    ),
    operation(
        "Recent-open-access Atom feed",
        method="GET",
        path="/feed/oa",
        accept=ATOM,
        status=200,
        response_media="application/atom+xml",
        limitation="application/json Accept returns HTTP 406.",
    ),
    operation(
        "Organization Atom feed",
        method="GET",
        path="/feed/organization/{ouId}",
        parameters=["ouId"],
        accept=ATOM,
        status=200,
        response_media="application/atom+xml",
        limitation="application/json Accept returns HTTP 406.",
    ),
    operation(
        "Search Atom feed",
        method="GET",
        path="/feed/search",
        parameters=["q"],
        accept=ATOM,
        status=500,
        public=False,
        response_media="application/json",
        limitation="Endpoint is anonymously reachable, but live probing returned HTTP 500 JsonParsingException for normal q values.",
    ),
    operation("Service info", method="GET", path="/miscellaneous/serviceInfo", status=200),
    operation(
        "Public sitemap",
        method="GET",
        path="/miscellaneous/{sitemapFile}",
        parameters=["sitemapFile"],
        status=200,
        response_media="application/xml",
    ),
    operation("Anonymous session status", method="GET", path="/login/who", status=200),
    operation("Logout anonymous session", method="GET", path="/logout", status=200, response_media=TEXT),
]


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
