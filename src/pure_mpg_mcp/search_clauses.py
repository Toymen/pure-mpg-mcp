"""Bespoke search-clause builders for criteria too irregular for a simple field map."""

from __future__ import annotations

from typing import Any


def organization_clause(organization: str) -> dict[str, Any]:
    """"Organisation" — OU id (incl. sub-units via identifierPath) or name."""
    if organization.startswith("ou_"):
        return {
            "bool": {
                "should": [
                    {"term": {"metadata.creators.person.organizations.identifier": organization}},
                    {"term": {"metadata.creators.person.organizations.identifierPath": organization}},
                ],
                "minimum_should_match": 1,
            }
        }
    return {"match": {"metadata.creators.person.organizations.name": organization}}


def identifier_clause(identifier: str) -> dict[str, Any]:
    """"Identifikatoren" — DOI, ISBN, ISSN, arXiv, PMID, …"""
    return {
        "bool": {
            "should": [
                {"term": {"metadata.identifiers.id.keyword": identifier}},
                {"match_phrase": {"metadata.identifiers.id": identifier}},
                {"match_phrase": {"metadata.sources.identifiers.id": identifier}},
            ],
            "minimum_should_match": 1,
        }
    }


def project_clause(project: str) -> dict[str, Any]:
    """"Projekt-Information" — title, grant id, funder, or program."""
    return {
        "bool": {
            "should": [
                {"match": {"metadata.projectInfo.title": project}},
                {"match": {"metadata.projectInfo.grantIdentifier": project}},
                {"match": {"metadata.projectInfo.fundingInfo.fundingOrganization.title": project}},
                {"match": {"metadata.projectInfo.fundingInfo.fundingProgram.title": project}},
            ],
            "minimum_should_match": 1,
        }
    }


def author_clause(author: str) -> dict[str, Any]:
    """"Urheber" — family or given name."""
    return {
        "multi_match": {
            "query": author,
            "fields": [
                "metadata.creators.person.familyName",
                "metadata.creators.person.givenName",
            ],
        }
    }


def fulltext_clause(fulltext: str) -> dict[str, Any]:
    """"Volltext" — text extracted from attached files."""
    return {
        "simple_query_string": {
            "query": fulltext,
            "fields": ["fulltext", "fulltexts", "fileData.content", "files.fileData.content"],
            "lenient": True,
        }
    }
