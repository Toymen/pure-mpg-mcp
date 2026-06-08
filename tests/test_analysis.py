"""Offline unit tests for the analysis, gender-cleaning, and CONE parsing logic."""

from pure_mpg_mcp import analysis
from pure_mpg_mcp.cone import ConeClient
from pure_mpg_mcp.gender import clean_given_name

REC = {
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
        "files": [{"metadata": {"visibility": "PUBLIC"}}],
    }
}


def test_year_and_open_access():
    assert analysis._year(REC) == "2021"
    assert analysis.is_open_access(REC) is True


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


def test_summarize_gender_threshold():
    authors = [
        {"gender": "male", "probability": 0.99},
        {"gender": "female", "probability": 0.55},  # below threshold -> unknown
        {"gender": None, "probability": None},
    ]
    s = analysis.summarize_gender(authors, threshold=0.6)
    assert s["male"] == 1
    assert s["female"] == 0
    assert s["unknown"] == 2


def test_clean_given_name():
    assert clean_given_name("Jan") == "Jan"
    assert clean_given_name("J.") is None
    assert clean_given_name("J") is None
    assert clean_given_name("Anne-Marie") == "Anne"
    assert clean_given_name("") is None
    assert clean_given_name(None) is None


def test_cone_clean_person():
    raw = {
        "http_xmlns_com_foaf_0_1_givenname": "Jan",
        "http_xmlns_com_foaf_0_1_family_name": "Stelzner",
        "http_purl_org_dc_elements_1_1_title": "Stelzner, Jan",
        "some_orcid_field": "0000-0002-1825-0097",
    }
    out = ConeClient._clean_person("persons314810", raw)
    assert out["givenName"] == "Jan"
    assert out["familyName"] == "Stelzner"
    assert out["orcid"] == "0000-0002-1825-0097"
