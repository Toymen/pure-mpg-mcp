"""Shared httpx.MockTransport wiring for offline Datasets source tests.

Response bodies are trimmed copies of real payloads captured from the live
APIs (2026-07-15) — see docs/research-data-discovery.md for the probes.
"""

from __future__ import annotations

import json

import httpx

ARTICLE_DOI = "10.1159/000553587"

SCHOLIX_TARGET_DATASET = {  # article as sourcePid -> dataset target
    "totalLinks": 1,
    "result": [
        {
            "RelationshipType": {"Name": "References"},
            "source": {"Type": "publication", "Identifier": [], "Title": "The article"},
            "target": {
                "Type": "dataset",
                "Identifier": [{"ID": "10.5061/dryad.abc", "IDScheme": "doi"}],
                "Title": "Dryad dataset",
                "Publisher": [{"name": "Dryad"}],
            },
        }
    ],
}

SCHOLIX_SOURCE_DATASET = {  # article as targetPid -> dataset source (IsSupplementTo)
    "totalLinks": 1,
    "result": [
        {
            "RelationshipType": {"Name": "IsSupplementTo"},
            "source": {
                "Type": "dataset",
                "Identifier": [{"ID": "10.21233/ms5z-v475", "IDScheme": "doi"}],
                "Title": "Supplement dataset",
                "Publisher": [{"name": "Unknown Repository"}],
            },
            "target": {"Type": "publication", "Identifier": [], "Title": "The article"},
        }
    ],
}

DATACITE_BY_DOI = {
    "data": [
        {
            "id": "10.6084/m9.figshare.32996252",
            "attributes": {
                "titles": [{"title": "Figshare supplement"}],
                "publisher": "figshare",
                "publicationYear": 2026,
                "relatedIdentifiers": [
                    {"relationType": "IsSupplementTo", "relatedIdentifier": ARTICLE_DOI}
                ],
            },
        }
    ],
    "meta": {"total": 1},
}

DATACITE_BY_ORCID = {
    "data": [
        {
            "id": "10.6084/m9.figshare.821213.v1",
            "attributes": {
                "titles": [{"title": "5000 random DOIs"}],
                "publisher": "figshare",
                "publicationYear": 2013,
                "relatedIdentifiers": [],
            },
        }
    ],
    "meta": {"total": 1},
}

B2FIND = {
    "success": True,
    "result": {
        "count": 1,
        "results": [
            {
                "title": "Ice thickness of Kilimanjaro",
                "name": "pkg-1",
                "extras": [
                    {"key": "DOI", "value": "https://doi.org/10.1594/pangaea.867908"},
                    {"key": "Publisher", "value": "PANGAEA"},
                    {"key": "PublicationYear", "value": "2016"},
                ],
            }
        ],
    },
}

CROSSREF_RELATION = {
    "message": {
        "relation": {
            "is-supplemented-by": [
                {"id": "10.1107/xyz/supp1", "id-type": "doi"},
                {"id": "urn:nbn:de:123", "id-type": "uri"},
            ]
        }
    }
}

ZENODO_BY_DOI = {
    "hits": {
        "total": 1,
        "hits": [
            {
                "doi": "10.5281/zenodo.111",
                "metadata": {"title": "Zenodo supplement", "publication_date": "2020-01-02"},
            }
        ],
    }
}

ZENODO_BY_ORCID = {
    "hits": {
        "total": 1,
        "hits": [
            {
                "doi": "10.5281/zenodo.222",
                "metadata": {"title": "Zenodo by author", "publication_date": "2021-05-05"},
            }
        ],
    }
}

FIGSHARE_BY_DOI = [
    {"doi": "10.6084/m9.figshare.5", "title": "S1 Table", "published_date": "2020-03-30T00:00:00Z"}
]

FIGSHARE_BY_ORCID = [
    {"doi": "10.6084/m9.figshare.6", "title": "Author dataset", "published_date": "2019-01-01T00:00:00Z"}
]

DRYAD = {
    "_embedded": {
        "stash:datasets": [
            {
                "identifier": "doi:10.5061/dryad.7rh4625",
                "title": "Matching Dryad dataset",
                "publicationDate": "2018-09-01",
                "relatedWorks": [
                    {"relationship": "primary_article", "identifier": ARTICLE_DOI}
                ],
            },
            {
                "identifier": "doi:10.5061/dryad.other",
                "title": "Unrelated fuzzy hit",
                "publicationDate": "2018-09-01",
                "relatedWorks": [
                    {"relationship": "primary_article", "identifier": "10.9999/other"}
                ],
            },
        ]
    }
}

OPENAIRE_BY_ORCID = {
    "header": {"numFound": 1},
    "results": [
        {
            "mainTitle": "OpenAIRE dataset",
            "pids": [{"scheme": "doi", "value": "10.6084/m9.figshare.107019.v2"}],
            "publicationDate": "2013-01-01",
            "publisher": "figshare",
        }
    ],
}

OPENALEX_BY_ORCID = {
    "meta": {"count": 1},
    "results": [
        {
            "doi": "https://doi.org/10.5281/zenodo.333",
            "display_name": "OpenAlex dataset",
            "publication_year": 2022,
        }
    ],
}


def datasets_handler(request: httpx.Request) -> httpx.Response:
    host, params = request.url.host, request.url.params
    if host == "api.scholexplorer.openaire.eu":
        if params.get("sourcePid"):
            return httpx.Response(200, json=SCHOLIX_TARGET_DATASET)
        return httpx.Response(200, json=SCHOLIX_SOURCE_DATASET)
    if host == "api.datacite.org":
        body = DATACITE_BY_DOI if "relatedIdentifiers" in params.get("query", "") else DATACITE_BY_ORCID
        return httpx.Response(200, json=body)
    if host == "b2find.eudat.eu":
        return httpx.Response(200, json=B2FIND)
    if host == "api.crossref.org":
        return httpx.Response(200, json=CROSSREF_RELATION)
    if host == "zenodo.org":
        body = ZENODO_BY_DOI if "related.identifier" in params.get("q", "") else ZENODO_BY_ORCID
        return httpx.Response(200, json=body)
    if host == "api.figshare.com":
        if request.method == "POST":
            assert ":orcid:" in json.loads(request.content)["search_for"]
            return httpx.Response(200, json=FIGSHARE_BY_ORCID)
        return httpx.Response(200, json=FIGSHARE_BY_DOI)
    if host == "datadryad.org":
        return httpx.Response(200, json=DRYAD)
    if host == "api.openaire.eu":
        return httpx.Response(200, json=OPENAIRE_BY_ORCID)
    if host == "api.openalex.org":
        return httpx.Response(200, json=OPENALEX_BY_ORCID)
    return httpx.Response(404)
