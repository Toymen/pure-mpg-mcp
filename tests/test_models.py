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


def test_summarize_item_surfaces_linked_research_data():
    """Research-data links live as a separate EXTERNAL_URL file component, not a
    dedicated relation field (PuRe's schema has none) — contentCategory +
    content must both surface so callers can find them."""
    rec = {
        "data": {
            "objectId": "item_3",
            "files": [
                {"objectId": "file_1", "storage": "INTERNAL_MANAGED", "content": "/rest/items/item_3/component/file_1/content", "metadata": {"contentCategory": "publisher-version"}},
                {"objectId": "file_2", "storage": "EXTERNAL_URL", "content": "https://osf.io/gbsf2/", "metadata": {"contentCategory": "research-data"}},
            ],
        }
    }
    out = summarize_item(rec)
    data_file = next(f for f in out["files"] if f["contentCategory"] == "research-data")
    assert data_file["storage"] == "EXTERNAL_URL"
    assert data_file["content"] == "https://osf.io/gbsf2/"


def test_summarize_search_shape():
    payload = {"numberOfRecords": 1, "records": [{"data": {"objectId": "item_9"}}]}
    out = summarize_search(payload)
    assert out["numberOfRecords"] == 1
    assert out["items"][0]["itemId"] == "item_9"
