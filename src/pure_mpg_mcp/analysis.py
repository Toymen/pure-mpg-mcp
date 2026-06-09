"""Client-side analytics over fetched PuRe records.

PuRe's search endpoint strips Elasticsearch aggregations, so these helpers
compute distributions, co-authorship, and open-access ratios from a fetched
record set. Pure functions — no I/O — so they are easy to test offline.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def clean_given_name(given: str | None) -> str | None:
    """Return a usable first name, or None if it's empty or a bare initial.

    Takes the first whitespace/hyphen token, strips punctuation, and drops bare
    initials ("J", "J.") which carry no usable signal.
    """
    if not given or not given.strip():
        return None
    token = given.strip().replace("-", " ").split()[0].strip(".,;").strip()
    if len(token) <= 1:
        return None
    if len(token) == 2 and token.endswith("."):
        return None
    return token


def _data(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("data", record)


def _md(record: dict[str, Any]) -> dict[str, Any]:
    return _data(record).get("metadata", {}) or {}


def _year(record: dict[str, Any]) -> str | None:
    md = _md(record)
    for field in ("datePublishedInPrint", "datePublishedOnline", "dateAccepted"):
        val = md.get(field)
        if isinstance(val, str) and len(val) >= 4 and val[:4].isdigit():
            return val[:4]
    return None


def creators(record: dict[str, Any], role: str = "AUTHOR") -> list[dict[str, Any]]:
    """Return person creators (optionally filtered by role)."""
    out = []
    for c in _md(record).get("creators", []) or []:
        if role and c.get("role") and c["role"] != role:
            continue
        person = c.get("person")
        if person:
            out.append(person)
    return out


def is_open_access(record: dict[str, Any]) -> bool:
    """A record counts as OA if any file component is publicly visible or CC-licensed."""
    for comp in _data(record).get("files", []) or []:
        if (comp.get("visibility") or "").upper() == "PUBLIC":
            return True
        fmd = comp.get("metadata", {}) or {}
        lic = (fmd.get("license") or "").lower()
        if "creativecommons.org" in lic:
            return True
    return False


def distribution(records: list[dict[str, Any]], group_by: str, top: int = 20) -> dict[str, Any]:
    """Counts grouped by one of: year, genre, language, organization, open_access."""
    counter: Counter[str] = Counter()
    for r in records:
        md = _md(r)
        if group_by == "year":
            key = _year(r)
            if key:
                counter[key] += 1
        elif group_by == "genre":
            counter[md.get("genre") or "UNKNOWN"] += 1
        elif group_by == "language":
            langs = md.get("languages") or []
            counter[(langs[0] if langs else "UNKNOWN")] += 1
        elif group_by == "open_access":
            counter["open_access" if is_open_access(r) else "closed"] += 1
        elif group_by == "organization":
            seen = set()
            for p in creators(r):
                for org in p.get("organizations", []) or []:
                    name = org.get("name")
                    if name and name not in seen:
                        seen.add(name)
                        counter[name] += 1
        else:
            raise ValueError(f"unknown group_by: {group_by}")
    items = counter.most_common(top) if group_by != "year" else sorted(counter.items())
    return {
        "groupBy": group_by,
        "analyzedRecords": len(records),
        "buckets": [{"key": k, "count": v} for k, v in items],
    }


def coauthorship(records: list[dict[str, Any]], top: int = 25) -> dict[str, Any]:
    """Top collaborating authors and institutions across the record set."""
    authors: Counter[str] = Counter()
    institutions: Counter[str] = Counter()
    team_sizes: list[int] = []
    for r in records:
        people = creators(r)
        team_sizes.append(len(people))
        seen_org = set()
        for p in people:
            fam = p.get("familyName")
            giv = p.get("givenName")
            if fam:
                authors[f"{fam}, {giv}" if giv else fam] += 1
            for org in p.get("organizations", []) or []:
                name = org.get("name")
                if name and name not in seen_org:
                    seen_org.add(name)
                    institutions[name] += 1
    avg_team = round(sum(team_sizes) / len(team_sizes), 2) if team_sizes else 0
    return {
        "analyzedRecords": len(records),
        "averageAuthorsPerPublication": avg_team,
        "soloAuthored": sum(1 for s in team_sizes if s == 1),
        "topAuthors": [{"author": a, "publications": n} for a, n in authors.most_common(top)],
        "topInstitutions": [{"institution": i, "publications": n} for i, n in institutions.most_common(top)],
    }
