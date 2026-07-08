"""Small record/query builders shared across offline test modules."""

from __future__ import annotations


def _search_payload(*item_ids: str, total: int | None = None) -> dict:
    return {
        "numberOfRecords": total if total is not None else len(item_ids),
        "records": [{"data": {"objectId": iid, "metadata": {"title": iid}}} for iid in item_ids],
    }


def _dated_record(field: str, date: str) -> dict:
    return {"numberOfRecords": 1, "records": [{"data": {"metadata": {field: date}}}]}


def _year_of_filter(query: dict) -> str:
    """Extract the queried year from a _date_clause filter (bool/should of ranges)."""
    filt = query["bool"]["filter"][0]
    clause = filt["bool"]["should"][0] if "bool" in filt else filt
    return next(iter(clause["range"].values()))["gte"][:4]


def _record_with_creators(*orgs: str) -> dict:
    return {
        "data": {
            "objectId": "item_x",
            "metadata": {
                "creators": [
                    {
                        "role": "AUTHOR",
                        "person": {"familyName": "Planck", "organizations": [{"name": o} for o in orgs]},
                    }
                ]
            },
        }
    }


def _authored_record(given: str | None, cone_id: str | None = None) -> dict:
    person: dict = {"familyName": "Planck", "givenName": given}
    if cone_id:
        person["identifier"] = {"id": cone_id}
    return {"data": {"objectId": "item_a", "metadata": {"creators": [{"person": person}]}}}


def _item_with_doi(doi: str | None) -> dict:
    identifiers = [{"type": "DOI", "id": doi}] if doi else []
    return {
        "objectId": "item_d",
        "metadata": {"title": "T", "identifiers": identifiers},
        "files": [
            {"objectId": "comp_1", "metadata": {"visibility": "PUBLIC", "title": "paper.pdf"}},
            {"objectId": "comp_2", "metadata": {"visibility": "PRIVATE"}},
        ],
    }


ANALYSIS_RECORD = {
    "data": {
        "objectId": "item_1",
        "metadata": {
            "genre": "ARTICLE",
            "languages": ["eng"],
            "datePublishedInPrint": "2021-03-01",
            "creators": [
                {
                    "role": "AUTHOR",
                    "person": {
                        "givenName": "Jan",
                        "familyName": "Stelzner",
                        "organizations": [{"name": "Max Planck Institute X"}],
                    },
                },
                {
                    "role": "AUTHOR",
                    "person": {
                        "givenName": "V.",
                        "familyName": "Meyer",
                        "organizations": [{"name": "Universität Hamburg"}],
                    },
                },
            ],
        },
        "files": [{"visibility": "PUBLIC", "metadata": {}}],
    }
}
