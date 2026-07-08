"""Aggregate analytics over a fetched record set: distributions and co-authorship."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .records import _md, _year, creators, is_open_access


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
            if fam and p.get("type") != "ORGANIZATION":
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
