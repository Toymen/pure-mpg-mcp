"""Offline tests for the record/search summarization helpers."""

from __future__ import annotations

from pure_mpg_mcp.models import summarize_item, summarize_search


def test_summarize_item_minimal():
    rec = {
        "data": {
            "objectId": "item_1",
            "objectPid": "hdl:123",
            "publicState": "RELEASED",
            "metadata": {
                "title": "A Title",
                "genre": "ARTICLE",
                "creators": [
                    {"person": {"familyName": "Planck", "givenName": "Max"}}
                ],
                "identifiers": [{"type": "DOI", "id": "10.1/x"}],
            },
        }
    }
    out = summarize_item(rec)
    assert out["itemId"] == "item_1"
    assert out["title"] == "A Title"
    assert out["creators"] == ["Planck, Max"]
    assert out["doi"] == "10.1/x"


def test_summarize_item_includes_organization_creators():
    """PubMan creators can be PERSON or ORGANIZATION (corporate authors) — both must show up."""
    rec = {
        "data": {
            "objectId": "item_2",
            "metadata": {
                "title": "A Report",
                "creators": [
                    {"type": "PERSON", "person": {"familyName": "Planck", "givenName": "Max"}},
                    {"type": "ORGANIZATION", "organization": {"name": "Max Planck Society"}},
                ],
            },
        }
    }
    out = summarize_item(rec)
    assert out["creators"] == ["Planck, Max", "Max Planck Society"]


def test_summarize_search_shape():
    payload = {"numberOfRecords": 1, "records": [{"data": {"objectId": "item_9"}}]}
    out = summarize_search(payload)
    assert out["numberOfRecords"] == 1
    assert out["items"][0]["itemId"] == "item_9"
