"""Shared ids and helpers for the opt-in live (network) critical-tool checks."""

from __future__ import annotations

LIVE_DOI = "10.1111/j.1467-7687.2008.00820.x"
LIVE_ITEM_ID = "item_1552993"
LIVE_FILE_ITEM_ID = "item_1554385"
LIVE_FILE_ID = "file_2123384"
LIVE_OU_ID = "ou_1497640"
LIVE_CONTEXT_ID = "ctx_1835112"


def identifier_query() -> dict:
    return {
        "bool": {
            "should": [
                {"term": {"metadata.identifiers.id.keyword": LIVE_DOI}},
                {"match_phrase": {"metadata.identifiers.id": LIVE_DOI}},
            ],
            "minimum_should_match": 1,
        }
    }


def assert_feed(text: str) -> None:
    assert text.lstrip().startswith("<?xml")
    assert "<feed" in text[:500]
