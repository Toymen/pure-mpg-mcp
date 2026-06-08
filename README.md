# pure-mpg-mcp

[![PyPI](https://img.shields.io/pypi/v/pure-mpg-mcp.svg)](https://pypi.org/project/pure-mpg-mcp/)
[![CI](https://github.com/Toymen/pure-mpg-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Toymen/pure-mpg-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<!-- mcp-name: io.github.toymen/pure-mpg-mcp -->

An [MCP](https://modelcontextprotocol.io) server for the **PuRe (PubMan) REST API** — the Max Planck Society's publication repository at [pure.mpg.de](https://pure.mpg.de).

It lets any MCP client (Claude Desktop, Claude Code, etc.) search and retrieve Max Planck publications, organizational units, collections, and feeds.

> **Public & read-only.** This server is anonymous: it only reaches `RELEASED`, publicly visible records. It does **not** log in, write, or access embargoed/private content. The PuRe write/curation/admin endpoints require authorization and are intentionally not exposed.

> **PuRe is the center.** Every tool starts from a PuRe record. A few tools *enrich* that record with other free public scholarly APIs (CONE, OpenAlex, Crossref, Unpaywall, Semantic Scholar), but always keyed on identifiers PuRe itself provides (DOI, person ids). The external sources are enrichment only — never queried on their own, never the canonical record.

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
| `analyze_authors` | Extract & enrich authors of a publication/query — full names (initials expanded via CONE), ORCID, affiliation |

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

Citation counts differ across sources because each indexes a different corpus — that's expected, and why `get_citation_metrics` shows them side by side rather than picking one.

> **Note on analytics.** PuRe's search endpoint strips Elasticsearch aggregations, so `publication_statistics` and `coauthorship_analysis` fetch a capped sample of records (scrolled, default 300–500) and aggregate **client-side**. When `numberOfRecords` exceeds the cap, treat the figures as sample-based, and raise `max_records` if you need more (at the cost of more requests).

## Use with Claude

The server is on PyPI, so no cloning or building is needed — clients run it
on demand with [`uvx`](https://docs.astral.sh/uv/).

**Prerequisite:** install [uv](https://docs.astral.sh/uv/) (provides `uvx`):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS/Linux
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Claude Code

One command:

```bash
claude mcp add pure-mpg -- uvx pure-mpg-mcp
```

To enable the Unpaywall full-text source as well, pass a real contact email:

```bash
claude mcp add pure-mpg -e PURE_CONTACT_EMAIL=you@example.org -- uvx pure-mpg-mcp
```

### Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config, or):

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "pure-mpg": {
      "command": "uvx",
      "args": ["pure-mpg-mcp"],
      "env": { "PURE_CONTACT_EMAIL": "you@example.org" }
    }
  }
}
```

Then **fully quit and reopen** Claude Desktop (closing the window isn't enough).
The `env` block is optional — it only enables the Unpaywall source.

### Remote connector by URL (no local install)

If you can't run it locally, host it once and add it to Claude as a **custom
connector by URL** — works in Claude Desktop *and* claude.ai (web), on Free/Pro/
Max/Team/Enterprise. No OAuth is required because the server is public and
read-only.

The same server speaks Streamable HTTP when `MCP_TRANSPORT=http` is set; the
endpoint is `/mcp`. A [`Dockerfile`](Dockerfile) and a Render blueprint
([`render.yaml`](render.yaml)) are included.

**Deploy (Render free tier, no terminal):**
1. Push/fork this repo, go to [render.com](https://render.com) → **New → Blueprint** → pick the repo.
2. Render reads `render.yaml` and deploys the container. (Optional: set `PURE_CONTACT_EMAIL` to enable Unpaywall.)
3. Your URL is `https://<service-name>.onrender.com/mcp`.

Any container host works equally well — Fly.io, Google Cloud Run, Railway,
Hugging Face Spaces — using the same `Dockerfile`. Locally:
`docker run -e MCP_TRANSPORT=http -p 8000:8000 <image>` → `http://localhost:8000/mcp`.

**Add it in Claude:** Settings → **Connectors** → **Add custom connector** →
paste the `…/mcp` URL → Transport: **Streamable HTTP** → Add.

> Note: Render's free tier sleeps after ~15 min idle, so the first request after
> a pause is slow (cold start) but works. For always-on, use a paid tier or a
> scale-to-zero host like Cloud Run.

### From source (development)

```bash
git clone https://github.com/Toymen/pure-mpg-mcp.git
cd pure-mpg-mcp
uv pip install -e ".[dev]"
```

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `PURE_BASE_URL` | `https://pure.mpg.de/rest` | Override the API base (e.g. a QA instance) |
| `PURE_CONE_URL` | `https://pure.mpg.de/cone` | Override the CONE authority base |
| `PURE_CONTACT_EMAIL` | _(unset)_ | A real contact email. Used for the OpenAlex/Crossref "polite pool", and **required by Unpaywall** — `find_full_text` and `enrich_publication` skip the Unpaywall source (and say so) until this is set. `@example.com` addresses are treated as unset. |

## Example

> "Find recent open-access articles from the Max Planck Institute for Evolutionary Anthropology about Neanderthals, and give me the BibTeX for the top hit."

The agent calls `search_publications(text="Neanderthal", genre="ARTICLE")`,
then `export_publication(item_id, format="BibTex")`.

## Development

```bash
uv pip install -e ".[dev]"
ruff check .
pytest -m "not network"   # offline unit tests (what CI runs)
pytest                     # include live API smoke tests (network)
```

Tests are split with a `network` marker: offline tests cover all the pure
aggregation/parsing logic and run in CI; network-marked tests hit the live
public APIs and are skipped in CI so the suite never depends on third-party
uptime or rate limits. GitHub Actions runs lint + offline tests on Python 3.10
and 3.12 ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Releases & publishing

Versioning and changelogs are automated with
[release-please](https://github.com/googleapis/release-please) from
[Conventional Commits](https://www.conventionalcommits.org/) — see
[CONTRIBUTING.md](CONTRIBUTING.md). The flow:

1. **Land Conventional Commits on `main`** (`feat:`, `fix:`, …).
2. **release-please opens a release PR** that bumps the version across
   `pyproject.toml`, `src/pure_mpg_mcp/__init__.py`, and [`server.json`](server.json),
   and updates [`CHANGELOG.md`](CHANGELOG.md)
   ([`.github/workflows/release-please.yml`](.github/workflows/release-please.yml)).
3. **Merge the release PR** → the tag and GitHub Release are created, and the
   package is built and pushed to **PyPI** via
   [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no
   stored token). No manual tagging.

MCP servers aren't "hosted" on GitHub — GitHub holds the source, PyPI ships the
package (`uvx pure-mpg-mcp`), and clients launch it locally over stdio. For
discovery, the optional **MCP Registry** uses [`server.json`](server.json) as
its manifest; the `<!-- mcp-name: io.github.toymen/pure-mpg-mcp -->` line in
this README verifies ownership. Publish it with the
[`mcp-publisher`](https://modelcontextprotocol.io/registry/quickstart) CLI once
a PyPI release exists.

> [`.github/workflows/publish.yml`](.github/workflows/publish.yml) remains as a
> fallback that publishes any **manually** created GitHub Release.

## API reference

- Swagger UI: <https://pure.mpg.de/rest/swagger-ui/index.html>
- OpenAPI spec: <https://pure.mpg.de/rest/v3/api-docs>
- PubMan REST docs: <https://colab.mpdl.mpg.de/mediawiki/PubMan_REST_API_Documentation>

## License

[MIT](LICENSE). This project is an independent client and is not affiliated with or endorsed by the Max Planck Society / Max Planck Digital Library.
