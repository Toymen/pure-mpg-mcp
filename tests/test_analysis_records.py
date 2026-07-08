"""Offline tests for per-record analysis helpers: creators, dates, open-access."""

from __future__ import annotations

from pure_mpg_mcp import analysis
from pure_mpg_mcp.analysis import clean_given_name

from helpers import ANALYSIS_RECORD as REC


def test_year_and_open_access():
    assert analysis._year(REC) == "2021"
    assert analysis.is_open_access(REC) is True


def test_closed_access_locator_is_not_open_access():
    """A PUBLIC-visibility locator pointing at a paywalled page must not count as OA."""
    locator_only = {"data": {"files": [{"visibility": "PUBLIC", "oaStatus": "CLOSED_ACCESS", "metadata": {}}]}}
    assert analysis.is_open_access(locator_only) is False

    mixed = {
        "data": {
            "files": [
                {"visibility": "PUBLIC", "oaStatus": "CLOSED_ACCESS", "metadata": {}},
                {"visibility": "PUBLIC", "oaStatus": "GOLD", "metadata": {}},
            ]
        }
    }
    assert analysis.is_open_access(mixed) is True


def test_is_open_access_uses_comp_visibility():
    """OA check reads visibility from the component root, not component.metadata."""
    rec_oa = {"data": {"files": [{"visibility": "PUBLIC", "metadata": {}}]}}
    rec_closed = {"data": {"files": [{"visibility": "PRIVATE", "metadata": {}}]}}
    rec_no_files = {"data": {"files": []}}

    assert analysis.is_open_access(rec_oa) is True
    assert analysis.is_open_access(rec_closed) is False
    assert analysis.is_open_access(rec_no_files) is False


def test_creators_includes_every_role_by_default():
    rec = {
        "data": {
            "metadata": {
                "creators": [
                    {"role": "EDITOR", "person": {"familyName": "Editorson"}},
                    {"role": "AUTHOR", "person": {"familyName": "Authorman"}},
                    {"role": "TRANSLATOR", "person": {"familyName": "Translated"}},
                ]
            }
        }
    }
    names = {p["familyName"] for p in analysis.creators(rec)}
    assert names == {"Editorson", "Authorman", "Translated"}
    assert {p["familyName"] for p in analysis.creators(rec, roles=("AUTHOR",))} == {"Authorman"}
    # role is attached to each returned person
    by_name = {p["familyName"]: p["role"] for p in analysis.creators(rec)}
    assert by_name == {"Editorson": "EDITOR", "Authorman": "AUTHOR", "Translated": "TRANSLATOR"}


def test_creators_includes_organization_creators():
    """PubMan creators can be PERSON or ORGANIZATION (a corporate/institutional author)."""
    rec = {
        "data": {
            "metadata": {
                "creators": [
                    {"role": "AUTHOR", "type": "PERSON", "person": {"familyName": "Planck", "givenName": "Max"}},
                    {"role": "AUTHOR", "type": "ORGANIZATION", "organization": {"name": "Max Planck Society"}},
                ]
            }
        }
    }
    people = analysis.creators(rec)
    assert len(people) == 2
    org = next(p for p in people if p["type"] == "ORGANIZATION")
    assert org["familyName"] == "Max Planck Society"
    assert org.get("givenName") is None


def test_clean_given_name():
    assert clean_given_name("Jan") == "Jan"
    assert clean_given_name("J.") is None
    assert clean_given_name("J") is None
    assert clean_given_name("Anne-Marie") == "Anne"
    assert clean_given_name("") is None
    assert clean_given_name(None) is None
