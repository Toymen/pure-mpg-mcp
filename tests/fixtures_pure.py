"""Shared httpx.MockTransport wiring for offline PureClient tests."""

from __future__ import annotations

import json

import httpx


def mock_transport(client_holder, handler, base_url="https://pure.test/rest") -> None:
    client_holder._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=base_url)


def pure_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/rest/items/search":
        body = json.loads(request.content)
        return httpx.Response(200, json={"numberOfRecords": 1, "records": [], "echo": body})
    if path == "/rest/items/search/scroll":
        return httpx.Response(200, json={"scrollId": request.url.params["scrollId"], "records": []})
    if path == "/rest/items/item_1":
        return httpx.Response(200, json={"objectId": "item_1"})
    if path == "/rest/items/item_1/export":
        return httpx.Response(200, text="@article{key}")
    if path == "/rest/items/item_1/component/comp_1/metadata":
        return httpx.Response(200, json={"visibility": "PUBLIC"})
    if path == "/rest/ous/search":
        return httpx.Response(200, json={"numberOfRecords": 2})
    if path == "/rest/ous/ou_1":
        return httpx.Response(200, json={"objectId": "ou_1"})
    if path == "/rest/ous/toplevel":
        return httpx.Response(200, json=[{"objectId": "ou_root"}])
    if path == "/rest/ous/firstlevel":
        return httpx.Response(200, json=[{"objectId": "ou_first"}])
    if path == "/rest/ous/ou_1/children":
        return httpx.Response(200, json=[{"objectId": "ou_child"}])
    if path == "/rest/ous/ou_1/idPath":
        return httpx.Response(200, json=["ou_1", "ou_root"])
    if path == "/rest/ous/ou_1/ouPath":
        return httpx.Response(200, json=["Dept", "Institute"])
    if path == "/rest/contexts/search":
        return httpx.Response(200, json={"numberOfRecords": 3})
    if path == "/rest/contexts/ctx_1":
        return httpx.Response(200, json={"objectId": "ctx_1"})
    if path == "/rest/feed/recent":
        return httpx.Response(200, text="<rss>recent</rss>")
    if path == "/rest/feed/oa":
        return httpx.Response(200, text="<rss>oa</rss>")
    if path == "/rest/feed/organization/ou_1":
        return httpx.Response(200, text="<rss>ou</rss>")
    if path == "/rest/feed/search":
        return httpx.Response(200, text=f"<rss>{request.url.params['q']}</rss>")
    if path == "/rest/miscellaneous/serviceInfo":
        return httpx.Response(200, text="")
    return httpx.Response(404)
