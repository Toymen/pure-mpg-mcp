"""OpenAPI operations for feeds, service info, sitemap, and session endpoints."""

from __future__ import annotations

from .common import ATOM, TEXT, operation

FEED_MISC_OPERATIONS = [
    operation(
        "Recent-publications Atom feed",
        method="GET",
        path="/feed/recent",
        accept=ATOM,
        status=200,
        response_media="application/atom+xml",
        limitation="application/json Accept returns HTTP 406.",
    ),
    operation(
        "Recent-open-access Atom feed",
        method="GET",
        path="/feed/oa",
        accept=ATOM,
        status=200,
        response_media="application/atom+xml",
        limitation="application/json Accept returns HTTP 406.",
    ),
    operation(
        "Organization Atom feed",
        method="GET",
        path="/feed/organization/{ouId}",
        parameters=["ouId"],
        accept=ATOM,
        status=200,
        response_media="application/atom+xml",
        limitation="application/json Accept returns HTTP 406.",
    ),
    operation(
        "Search Atom feed",
        method="GET",
        path="/feed/search",
        parameters=["q"],
        accept=ATOM,
        status=500,
        public=False,
        response_media="application/json",
        limitation="Endpoint is anonymously reachable, but live probing returned HTTP 500 JsonParsingException for normal q values.",
    ),
    operation("Service info", method="GET", path="/miscellaneous/serviceInfo", status=200),
    operation(
        "Public sitemap",
        method="GET",
        path="/miscellaneous/{sitemapFile}",
        parameters=["sitemapFile"],
        status=200,
        response_media="application/xml",
    ),
    operation("Anonymous session status", method="GET", path="/login/who", status=200),
    operation("Logout anonymous session", method="GET", path="/logout", status=200, response_media=TEXT),
]
