"""Shared httpx.MockTransport wiring for offline ConeClient tests."""

from __future__ import annotations

import httpx

CONE_PERSON = {
    "http://x/givenname": "Jan",
    "http://x/family_name": "Doe",
    "http://x/title": "Doe, Jan",
    "http://x/identifier": "https://orcid.org/0000-0001-2345-6789",
    "http://x/position": {"organization": "Max Planck Society, Some Institute"},
}


def cone_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/cone/persons/query":
        return httpx.Response(200, json=[{"id": "persons1", "type": "main", "value": "Doe, Jan"}])
    if request.url.path == "/cone/persons/resource/persons1":
        return httpx.Response(200, json=CONE_PERSON)
    if request.url.path == "/cone/iso639-3/all":
        return httpx.Response(200, json=[{"id": "eng", "value": "English"}, {"id": "deu", "value": "German"}])
    return httpx.Response(404)
