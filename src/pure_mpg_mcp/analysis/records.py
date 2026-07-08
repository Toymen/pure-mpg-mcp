"""Per-record helpers: creators, dates, open-access — no I/O, pure functions."""

from __future__ import annotations

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


def creators(
    record: dict[str, Any],
    roles: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Return every creator (person or organization) with `role`/`type` attached.

    Defaults to every role PubMan records (AUTHOR, EDITOR, TRANSLATOR,
    DIRECTOR, REFEREE, INVENTOR, ...) so nothing is silently dropped from
    aggregate views. Pass `roles` to narrow to a subset.

    A creator's `type` is PERSON or ORGANIZATION (a corporate/institutional
    author — PubMan allows both). Organization creators carry their name in
    `familyName` (with no `givenName`) so they don't vanish from person-shaped
    output; callers that only want individuals should filter on `type`.
    """
    out = []
    for c in _md(record).get("creators", []) or []:
        if roles and c.get("role") not in roles:
            continue
        person = c.get("person")
        if person:
            out.append({**person, "role": c.get("role"), "type": c.get("type", "PERSON")})
            continue
        org_name = (c.get("organization") or {}).get("name")
        if org_name:
            out.append({"familyName": org_name, "role": c.get("role"), "type": c.get("type", "ORGANIZATION")})
    return out


def is_open_access(record: dict[str, Any]) -> bool:
    """A record counts as OA if a file component is publicly visible or CC-licensed.

    Locators (external links) are always visibility=PUBLIC in PubMan, and can
    explicitly carry ``oaStatus: CLOSED_ACCESS`` — a public link to a paywalled
    publisher page. Those must not count as open access.
    """
    for comp in _data(record).get("files", []) or []:
        fmd = comp.get("metadata", {}) or {}
        oa_status = (comp.get("oaStatus") or fmd.get("oaStatus") or "").upper()
        if oa_status == "CLOSED_ACCESS":
            continue
        if (comp.get("visibility") or "").upper() == "PUBLIC":
            return True
        lic = (fmd.get("license") or "").lower()
        if "creativecommons.org" in lic:
            return True
    return False
