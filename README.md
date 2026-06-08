# pure-mpg-mcp

An [MCP](https://modelcontextprotocol.io) server for the **PuRe (PubMan) REST API** — the Max Planck Society's publication repository at [pure.mpg.de](https://pure.mpg.de).

It lets any MCP client (Claude Desktop, Claude Code, etc.) search and retrieve Max Planck publications, organizational units, collections, and feeds.

> **Public & read-only.** This server is anonymous: it only reaches `RELEASED`, publicly visible records. It does **not** log in, write, or access embargoed/private content. The PuRe write/curation/admin endpoints require authorization and are intentionally not exposed.

> **PuRe is the center.** Every tool starts from a PuRe record. A few tools *enrich* that record with other free public scholarly APIs (CONE, OpenAlex, Crossref, Unpaywall, Semantic Scholar, genderize.io), but always keyed on identifiers PuRe itself provides (DOI, person ids). The external sources are enrichment only — never queried on their own, never the canonical record.

## Tools

**Search & retrieval**

| Tool | What it does |
| --- | --- |
| `search_publications` | Search by free text, author, genre, and year (compact results) |
| `search_raw` | Run a raw Elasticsearch query for advanced cases |
| `get_publication` | Full metadata for one item id (e.g. `item_1552993`) |
| `find_by_doi` | Look up a publication by DOI (bare or doi.org URL) |
| `export_publication` | Export as BibTeX, citation, MARC, EndNote, … |
| `get_file_metadata` | Metadata for an attached file (component) |
| `search_organizations` | Search institutes / departments (organizational units) |
| `list_top_organizations` | Top-level organizational units |
| `search_collections` | Search contexts (collections) |
| `recent_publications` | Feed of recently released items |
| `open_access_feed` | Feed of recent open-access items |
| `service_info` | Version / status of the PuRe instance |

**Authority & analysis** (for bibliometrics)

| Tool | What it does |
| --- | --- |
| `resolve_author` | Resolve a name/person-id against the CONE authority → full name, affiliation, ORCID. Expands initials. |
| `author_publications` | List an author's publications (by CONE id or family name) |
| `publication_statistics` | Distributions over a result set: by `year`, `genre`, `language`, `organization`, or `open_access` |
| `coauthorship_analysis` | Collaboration patterns: avg team size, solo-authored count, top co-authors & institutions |
| `analyze_authors` | Extract & enrich authors of a publication/query — full names (initials expanded via CONE), ORCID, affiliation. Optional probabilistic gender enrichment (off by default; see caveats below) |

**External enrichment** (PuRe DOI → public scholarly APIs)

| Tool | What it does |
| --- | --- |
| `enrich_publication` | Attach external signals to a PuRe item: citations, topics, institutions (ROR), funders, license, OA full text. Pick `sources` from `openalex`, `crossref`, `unpaywall`, `semanticscholar` |
| `get_citation_metrics` | Citation counts for one publication side-by-side across OpenAlex, Crossref, and Semantic Scholar (incl. influential citations) |
| `find_full_text` | Locate free full text — PuRe's own public files first, then Unpaywall / OpenAlex open-access locations |

### Enrichment sources

All are free and require no authentication. They are queried **only** with an identifier taken from a PuRe record, and any source lacking that record is silently omitted.

| Source | Adds | Notes |
| --- | --- | --- |
| [CONE](https://pure.mpg.de/cone) | Full author names, ORCID, affiliation | MPG's own authority service |
| [OpenAlex](https://openalex.org) | Citation count, topics, institutions/ROR, OA status, related works | No key |
| [Crossref](https://www.crossref.org) | References, funders, license, citing count | No key |
| [Unpaywall](https://unpaywall.org) | Definitive OA status + free full-text PDF | Requires a contact email |
| [Semantic Scholar](https://www.semanticscholar.org) | Influential-citation count, TLDR summary | No key; rate-limited |
| [genderize.io](https://genderize.io) | Probabilistic gender (opt-in only) | See caveats below |

Citation counts differ across sources because each indexes a different corpus — that's expected, and why `get_citation_metrics` shows them side by side rather than picking one.

> **Note on analytics.** PuRe's search endpoint strips Elasticsearch aggregations, so `publication_statistics` and `coauthorship_analysis` fetch a capped sample of records (scrolled, default 300–500) and aggregate **client-side**. When `numberOfRecords` exceeds the cap, treat the figures as sample-based, and raise `max_records` if you need more (at the cost of more requests).

## Optional gender enrichment — methodology & ethics

`analyze_authors` can optionally attach a probabilistic gender guess to each author (`include_gender=True`, **off by default**). Gender-gap studies are a common, legitimate bibliometric task, but the enrichment carries real limitations:

- **Probabilistic and binary-by-construction.** Gender is inferred from first names via [genderize.io](https://genderize.io); the upstream service returns only male/female/unknown. Use it for **aggregate** analysis, **never** for claims about individuals.
- **Initials are resolved first.** PuRe often stores initials (`"J."`). With `enrich=True` (default), they are expanded to full first names via the CONE authority service before inference. Names that stay ambiguous, or fall below `probability_threshold` (default 0.6), are reported as **unknown** — and the unknown bucket is reported honestly, not hidden.
- **Country hint improves accuracy.** Pass `country_id` (ISO-3166 alpha-2, default `"DE"`). Accuracy is known to be weaker for East-Asian names ([Santamaría & Mihaljević 2018](https://doi.org/10.7717/peerj-cs.156)).
- **Rate limits.** genderize.io's free tier allows ~100 names/day with no key; set `GENDERIZE_API_KEY` to raise it. Results are cached in-process.

Only this opt-in path makes a third-party call (genderize.io). With `include_gender=False`, `analyze_authors` — like every other tool — talks only to public MPG endpoints.

## Install

Requires Python ≥ 3.10. Using [uv](https://docs.astral.sh/uv/):

```bash
uv pip install -e .
# or from PyPI once published:
# uv pip install pure-mpg-mcp
```

## Run

```bash
pure-mpg-mcp      # stdio transport
```

### Claude Desktop / Claude Code config

Add to your MCP config (`claude_desktop_config.json` or `.mcp.json`):

```json
{
  "mcpServers": {
    "pure-mpg": {
      "command": "pure-mpg-mcp"
    }
  }
}
```

If you installed into a virtualenv, point `command` at the venv's `pure-mpg-mcp`,
or use `uvx`:

```json
{
  "mcpServers": {
    "pure-mpg": {
      "command": "uvx",
      "args": ["pure-mpg-mcp"]
    }
  }
}
```

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `PURE_BASE_URL` | `https://pure.mpg.de/rest` | Override the API base (e.g. a QA instance) |
| `PURE_CONE_URL` | `https://pure.mpg.de/cone` | Override the CONE authority base |
| `PURE_CONTACT_EMAIL` | `pure-mpg-mcp@example.com` | Contact email sent to OpenAlex/Crossref polite pools and required by Unpaywall. Set to a real address. |
| `GENDERIZE_API_KEY` | _(unset)_ | Raise genderize.io rate limits for `analyze_authors`' optional gender enrichment |

## Example

> "Find recent open-access articles from the Max Planck Institute for Evolutionary Anthropology about Neanderthals, and give me the BibTeX for the top hit."

The agent calls `search_publications(text="Neanderthal", genre="ARTICLE")`,
then `export_publication(item_id, format="BibTex")`.

## Development

```bash
uv pip install -e ".[dev]"
ruff check .
pytest -m "not network"   # offline unit tests
pytest                     # include live API smoke tests
```

## API reference

- Swagger UI: <https://pure.mpg.de/rest/swagger-ui/index.html>
- OpenAPI spec: <https://pure.mpg.de/rest/v3/api-docs>
- PubMan REST docs: <https://colab.mpdl.mpg.de/mediawiki/PubMan_REST_API_Documentation>

## License

[MIT](LICENSE). This project is an independent client and is not affiliated with or endorsed by the Max Planck Society / Max Planck Digital Library.
