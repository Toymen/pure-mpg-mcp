"""Controlled vocabularies and search-field mappings for the PubMan JSON model."""

from __future__ import annotations

# Complete genre vocabulary from the PubMan JSON model.
_GENRES = [
    "ARTICLE", "BLOG_POST", "BOOK", "BOOK_ITEM", "BOOK_REVIEW", "CASE_NOTE",
    "CASE_STUDY", "COLLECTED_EDITION", "COMMENTARY", "CONFERENCE_PAPER",
    "CONFERENCE_REPORT", "CONTRIBUTION_TO_COLLECTED_EDITION",
    "CONTRIBUTION_TO_COMMENTARY", "CONTRIBUTION_TO_ENCYCLOPEDIA",
    "CONTRIBUTION_TO_FESTSCHRIFT", "CONTRIBUTION_TO_HANDBOOK",
    "COURSEWARE_LECTURE", "DATA_PUBLICATION", "EDITORIAL", "ENCYCLOPEDIA",
    "FESTSCHRIFT", "FILM", "HANDBOOK", "INTERVIEW", "ISSUE", "JOURNAL",
    "MAGAZINE_ARTICLE", "MANUAL", "MANUSCRIPT", "MEETING_ABSTRACT",
    "MONOGRAPH", "MULTI_VOLUME", "NEWSPAPER", "NEWSPAPER_ARTICLE", "OPINION",
    "OTHER", "PAPER", "PATENT", "POSTER", "PREPRINT",
    "PRE_REGISTRATION_PAPER", "PROCEEDINGS", "REGISTERED_REPORT", "REPORT",
    "REVIEW_ARTICLE", "SERIES", "SOFTWARE", "TALK_AT_EVENT", "THESIS",
]

_LANGUAGES = [
    "afr", "ara", "aze", "bel", "bos", "bul", "cat", "ces", "cym", "dan",
    "deu", "ell", "eng", "est", "eus", "fas", "fin", "fra", "gle", "glg",
    "heb", "hin", "hrv", "hun", "hye", "ind", "isl", "ita", "jpn", "kat",
    "kor", "lat", "lav", "lit", "mkd", "mlt", "msa", "nld", "nor", "pol",
    "por", "ron", "rus", "slk", "slv", "spa", "srp", "swe", "tha", "tur",
    "ukr", "urd", "vie", "zho",
]

_OA_STATUSES = ["GOLD", "GREEN", "HYBRID", "MISCELLANEOUS", "NOT_SPECIFIED", "CLOSED_ACCESS"]

_DATE_PUBLISHED = ["metadata.datePublishedInPrint", "metadata.datePublishedOnline"]

# Date criteria of the PubMan advanced search, mapped to index fields.
_DATE_FIELDS: dict[str, list[str]] = {
    "any": [
        "metadata.datePublishedInPrint", "metadata.datePublishedOnline",
        "metadata.dateAccepted", "metadata.dateSubmitted",
        "metadata.dateModified", "metadata.dateCreated",
    ],
    "published_in_print": ["metadata.datePublishedInPrint"],
    "published_online": ["metadata.datePublishedOnline"],
    "accepted": ["metadata.dateAccepted"],
    "submitted": ["metadata.dateSubmitted"],
    "modified": ["metadata.dateModified"],
    "created": ["metadata.dateCreated"],
    "modified_internal": ["lastModificationDate"],
    "created_internal": ["creationDate"],
    "event_start": ["metadata.event.startDate"],
    "event_end": ["metadata.event.endDate"],
}

# Search criteria that translate straight to a single `match` clause —
# "PuRe field name" -> "ES field path".
_MATCH_FIELDS = {
    "title": "metadata.title",  # "Titel"
    "keyword": "metadata.freeKeywords",  # "Schlagwörter"
    "classification": "metadata.subjects.value",  # "Klassifikation" — controlled subjects
    "source": "metadata.sources.title",  # "Quelle"/"Zeitschrift"
    "local_tag": "localTags",  # "Lokale Tags"
    "event": "metadata.event.title",  # "Titel der Veranstaltung"
}

# Search criteria that translate to a single `term` clause (exact match).
# "PuRe field name" -> (ES field path, uppercase the value first).
_TERM_FIELDS = {
    "genre": ("metadata.genre", True),
    "review_method": ("metadata.reviewMethod", True),  # "Begutachtung" — PEER/INTERNAL/NO_REVIEW
    "language": ("metadata.languages", False),  # ISO 639-3, e.g. "eng", "deu"
}
