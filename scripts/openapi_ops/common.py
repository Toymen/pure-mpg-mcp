"""Shared OpenAPI building blocks: parameters, response envelopes, the operation() builder."""

from __future__ import annotations

from typing import Any

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
