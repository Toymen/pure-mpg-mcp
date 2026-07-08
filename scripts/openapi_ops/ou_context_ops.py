"""OpenAPI operations for the /ous/* and /contexts/* surface."""

from __future__ import annotations

from .common import SEARCH_BODY, TEXT, operation

OU_CONTEXT_OPERATIONS = [
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
]
