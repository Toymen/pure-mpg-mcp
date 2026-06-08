"""Probabilistic gender inference for author given names via genderize.io.

This is an **opt-in enrichment**, not a core PuRe capability. PuRe stores no
gender field; the only signal available is the author's given name.

Methodological notes (following Santamaria & Mihaljevic 2018 and the
genderizeR literature):
  * Names are cleaned: take the first whitespace/hyphen token, strip
    punctuation, drop bare initials (a single letter, optionally dotted) since
    they carry no gender signal.
  * A country hint (ISO-3166 alpha-2, e.g. "DE") materially improves accuracy
    and is passed through when provided.
  * Results are probabilistic and *binary-by-construction* (the upstream
    service only returns male/female/unknown). Always surfaced with the
    ``probability`` and sample ``count`` so callers can threshold and so
    aggregate analysis can honestly report an "unknown" bucket. Do not use for
    decisions about individuals.

genderize.io's free tier allows ~100 names/day with no key. Set
``GENDERIZE_API_KEY`` to raise the limit. Names are batched (10 per request)
and cached in-process to avoid redundant calls.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_API = "https://api.genderize.io"
_cache: dict[tuple[str, str | None], dict[str, Any]] = {}


def clean_given_name(given: str | None) -> str | None:
    """Return a usable first name, or None if it's empty / a bare initial."""
    if not given:
        return None
    token = given.strip().replace("-", " ").split()[0] if given.strip() else ""
    token = token.strip(".,;").strip()
    if len(token) <= 1:  # "J", "J." -> no signal
        return None
    if len(token) == 2 and token.endswith("."):
        return None
    return token


async def genderize(
    names: list[str],
    country_id: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, dict[str, Any]]:
    """Resolve a list of cleaned first names to gender predictions.

    Returns {name: {gender, probability, count}}. Uses an in-process cache and
    batches requests (10 names each). ``gender`` may be None (unknown).
    """
    owns = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    api_key = os.getenv("GENDERIZE_API_KEY")
    out: dict[str, dict[str, Any]] = {}
    todo: list[str] = []
    for n in names:
        key = (n.lower(), country_id)
        if key in _cache:
            out[n] = _cache[key]
        elif n not in todo:
            todo.append(n)
    try:
        for i in range(0, len(todo), 10):
            batch = todo[i : i + 10]
            params: list[tuple[str, str]] = [("name[]", n) for n in batch]
            if country_id:
                params.append(("country_id", country_id))
            if api_key:
                params.append(("apikey", api_key))
            resp = await client.get(_API, params=params)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):  # single-name responses aren't wrapped in a list
                data = [data]
            for entry in data:
                rec = {
                    "gender": entry.get("gender"),
                    "probability": entry.get("probability"),
                    "count": entry.get("count"),
                }
                name = entry.get("name", "")
                out[name] = rec
                _cache[(name.lower(), country_id)] = rec
    finally:
        if owns:
            await client.aclose()
    return out
