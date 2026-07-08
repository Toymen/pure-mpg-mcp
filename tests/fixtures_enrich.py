"""Shared httpx.MockTransport wiring for offline Enrichment source tests."""

from __future__ import annotations

import httpx

OPENALEX = {
    "id": "https://openalex.org/W1",
    "cited_by_count": 12,
    "open_access": {"oa_status": "gold"},
    "topics": [{"display_name": "Physics"}],
    "authorships": [{"institutions": [{"display_name": "MPI X", "ror": "https://ror.org/r1"}]}],
    "referenced_works": ["W2"],
    "related_works": ["W3"],
}

CROSSREF = {
    "message": {
        "is-referenced-by-count": 8,
        "references-count": 30,
        "funder": [{"name": "DFG"}],
        "license": [{"URL": "https://cc.org/by"}],
        "publisher": "ACS",
        "container-title": ["Journal of Tests"],
    }
}

UNPAYWALL = {
    "is_oa": True,
    "oa_status": "green",
    "best_oa_location": {"url": "u", "url_for_pdf": "u.pdf", "host_type": "repository", "license": "cc-by"},
}

S2 = {
    "citationCount": 9,
    "influentialCitationCount": 2,
    "fieldsOfStudy": ["Physics"],
    "tldr": {"text": "Short summary."},
}


def enrich_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "api.openalex.org":
        return httpx.Response(200, json=OPENALEX)
    if host == "api.crossref.org":
        return httpx.Response(200, json=CROSSREF)
    if host == "api.unpaywall.org":
        return httpx.Response(200, json=UNPAYWALL)
    if host == "api.semanticscholar.org":
        return httpx.Response(200, json=S2)
    return httpx.Response(404)
