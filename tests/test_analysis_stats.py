"""Offline tests for aggregate analysis helpers: distributions and co-authorship."""

from __future__ import annotations

from pure_mpg_mcp import analysis

from helpers import ANALYSIS_RECORD as REC


def test_coauthorship_excludes_organization_creators_from_top_authors():
    rec = {
        "data": {
            "metadata": {
                "creators": [
                    {"type": "PERSON", "person": {"familyName": "Planck", "givenName": "Max"}},
                    {"type": "ORGANIZATION", "organization": {"name": "Max Planck Society"}},
                ]
            }
        }
    }
    c = analysis.coauthorship([rec])
    assert c["averageAuthorsPerPublication"] == 2.0  # org creator still counts toward team size
    assert [a["author"] for a in c["topAuthors"]] == ["Planck, Max"]  # but not the person-name leaderboard


def test_distribution_genre_and_org():
    d = analysis.distribution([REC], group_by="genre")
    assert d["buckets"][0] == {"key": "ARTICLE", "count": 1}
    orgs = analysis.distribution([REC], group_by="organization")
    names = {b["key"] for b in orgs["buckets"]}
    assert "Max Planck Institute X" in names


def test_coauthorship_team_size():
    c = analysis.coauthorship([REC])
    assert c["averageAuthorsPerPublication"] == 2.0
    assert c["soloAuthored"] == 0
