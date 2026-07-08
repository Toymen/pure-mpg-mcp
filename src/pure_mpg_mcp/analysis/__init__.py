"""Client-side analytics over fetched PuRe records.

PuRe's search endpoint strips Elasticsearch aggregations, so these helpers
compute distributions, co-authorship, and open-access ratios from a fetched
record set. Pure functions — no I/O — so they are easy to test offline.
"""

from __future__ import annotations

from .records import _data, _md, _year, clean_given_name, creators, is_open_access
from .stats import coauthorship, distribution

__all__ = [
    "clean_given_name",
    "creators",
    "is_open_access",
    "distribution",
    "coauthorship",
    "_data",
    "_md",
    "_year",
]
