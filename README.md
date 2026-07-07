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
| `search_publications` | Search with every field of the PuRe advanced search: text, title, keyword (Schlagwörter), classification, fulltext, author, orcid, organization, genre, review method, language, source/journal, identifier, local tag, collection, project info, event, and any of the 9 date criteria |
| `search_raw` | Run a raw Elasticsearch query for advanced cases |
| `get_publication` | Full metadata for one item id (e.g. `item_1552993`) |
| `find_by_doi` | Look up a publication by DOI (bare or doi.org URL) |
| `export_publication` | Export one item as BibTeX, citation, MARC, EndNote, … |
| `export_search_results` | Bulk-export a whole search result set in one call (up to 5000 records) |
| `get_file_metadata` | Metadata for an attached file (component), plus its content/thumbnail URLs |
| `search_organizations` | Search institutes / departments (organizational units) |
| `get_organization` | One organizational unit by id |
| `list_top_organizations` | Top-level organizational units |
| `list_first_level_organizations` | First-level organizational units |
| `organization_children` | Direct child units of an organizational unit |
| `organization_hierarchy` | Ancestor path (id + name) from a unit up to its root institute |
| `search_collections` | Search contexts (collections) |
| `get_collection` | One context (collection) by id |
| `recent_publications` | Feed of recently released items |
| `open_access_feed` | Feed of recent open-access items |
| `organization_feed` | Feed of recent releases for one organizational unit |
| `search_feed` | Any search, rendered as an RSS/Atom feed |
| `service_info` | Version / status of the PuRe instance |

**Authority & analysis** (for bibliometrics)

| Tool | What it does |
| --- | --- |
| `resolve_author` | Resolve a name/person-id against the CONE authority → full name, affiliation, ORCID. Expands initials. |
| `author_publications` | List an author's publications (by CONE id or family name) |
| `list_languages` | Full ISO 639-3 language vocabulary from the CONE authority (id + display name) |
| `publication_statistics` | Distributions over a result set: by `year`, `genre`, `language`, `organization`, `open_access`, or `oa_status` (gold/green/hybrid/…) |
| `coauthorship_analysis` | Collaboration patterns: avg team size, solo-authored count, top co-authors & institutions (authors and editors) |
| `analyze_authors` | Extract & enrich authors of a publication/query — full names (initials expanded via CONE), ORCID (inline or CONE), affiliation |

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

## Use with MCP clients

There are two ways to use this server:

1. **Local stdio**: the MCP client starts `pure-mpg-mcp` on your machine. This
   is the easiest path for Claude Code and Claude Desktop.
2. **Remote Streamable HTTP**: the server runs behind HTTPS and clients connect
   to `https://.../mcp`. This is required for ChatGPT custom apps/connectors and
   is also useful for Claude web or team-wide installs.

The server is published on PyPI, so most users do not need to clone this repo.
Clients can run it on demand with [`uvx`](https://docs.astral.sh/uv/).

**Install uv first** (it provides `uvx`):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### PyPI package

PyPI is the canonical distribution path for this MCP server. It hosts the
installable package named `pure-mpg-mcp`; MCP clients then start that package
locally.

For local MCP setup, there is no separate `<server>` URL or hosted endpoint to
fill in. The MCP client config should point to the PyPI command:

```bash
uvx pure-mpg-mcp
```

or pin a specific release:

```bash
uvx --from pure-mpg-mcp==0.1.3 pure-mpg-mcp
```

Package page: <https://pypi.org/project/pure-mpg-mcp/>

This is the right setup for Claude Code and Claude Desktop because they can
start local stdio MCP servers. ChatGPT cannot start a local PyPI package; for
ChatGPT, deploy the same package as an HTTPS Streamable HTTP server and use the
public `/mcp` URL.

### Quick smoke test

Before wiring an MCP client, confirm the package can start:

```bash
uvx pure-mpg-mcp
```

That command starts the stdio MCP server and waits for an MCP client. Stop it
with `Ctrl+C`. If it downloads and starts without an import error, the package is
installed correctly.

### Claude Code

Add the local stdio server:

```bash
claude mcp add pure-mpg -- uvx pure-mpg-mcp
```

To enable the Unpaywall full-text source, pass a real contact email:

```bash
claude mcp add pure-mpg -e PURE_CONTACT_EMAIL=you@example.org -- uvx pure-mpg-mcp
```

Then start a new Claude Code session and ask something that should require a
tool call, for example:

> Search PuRe for recent open-access articles about Neanderthals and export the
> top result as BibTeX.

Claude should discover tools such as `search_publications`,
`find_by_doi`, `export_publication`, and `publication_statistics`.

### Claude Desktop

Edit `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Use this config:

```json
{
  "mcpServers": {
    "pure-mpg": {
      "command": "uvx",
      "args": ["pure-mpg-mcp"],
      "env": {
        "PURE_CONTACT_EMAIL": "you@example.org"
      }
    }
  }
}
```

`mcpServers` is Claude Desktop's required config object. `pure-mpg` is just the
local name you give this MCP server inside Claude. The actual server comes from
PyPI via `uvx pure-mpg-mcp`; no URL is needed for this local setup.

The `env` block is optional. It only enables Unpaywall-backed full-text lookup;
the PuRe, CONE, OpenAlex, Crossref, and Semantic Scholar features work without
it.

After editing the file, **fully quit and reopen** Claude Desktop. Closing only
the window is not enough. In a new chat, ask Claude to search or retrieve a PuRe
publication and it should offer to use the `pure-mpg` MCP server.

### Claude by remote URL

If you cannot run local commands, host this server once and add it to Claude as a
custom connector by URL. The endpoint is `/mcp` over Streamable HTTP:

```text
https://<your-host>/mcp
```

No OAuth is required because this server is public, read-only, and anonymous.
In Claude, add a custom connector and choose **Streamable HTTP** as the
transport.

### ChatGPT

ChatGPT connects to MCP servers as custom apps/connectors over HTTPS. It cannot
start this package locally with stdio, so deploy the HTTP endpoint first. The
OpenAI Apps SDK documentation describes the ChatGPT flow as: make the MCP server
reachable over HTTPS, go to **Settings -> Connectors -> Create**, and enter the
public `/mcp` URL. See OpenAI's official docs:

- [Connect from ChatGPT](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt)
- [Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt)
- [Connectors in ChatGPT](https://help.openai.com/en/articles/11487775-connectors-in-chatgpt)

Steps:

1. Deploy this server with `MCP_TRANSPORT=http`.
2. Make sure the final URL is HTTPS and ends in `/mcp`.
3. In ChatGPT, enable developer mode if your plan/workspace requires it.
4. Go to **Settings -> Connectors -> Create**.
5. Enter a name such as `PuRe MPG Publications`.
6. Enter a description such as "Search and analyze public Max Planck Society publications from PuRe/PubMan."
7. Set the connector URL to `https://<your-host>/mcp`.
8. Create the connector. ChatGPT should show the tools advertised by the MCP
   server.
9. Start a new chat, open the tool/app picker, choose your connector, and ask a
   PuRe-related question.

Good first prompt:

> Use PuRe MPG Publications to find recent Max Planck open-access articles about
> quantum materials and summarize the top five results with DOIs.

If ChatGPT cannot create the connector, check that your ChatGPT plan/workspace
allows custom MCP apps/connectors and that workspace admins have enabled the
feature.

### Host the HTTP endpoint

The same Python server speaks Streamable HTTP at `/mcp` when
`MCP_TRANSPORT=http` is set. A [`Dockerfile`](Dockerfile) is included.

**Option A: Render** ([`render.yaml`](render.yaml))

Go to [render.com](https://render.com), choose **New -> Blueprint**, and select
this repo. Render builds the container and your MCP URL is:

```text
https://<service>.onrender.com/mcp
```

Render sets `RENDER_EXTERNAL_HOSTNAME`, which the server trusts as an allowed
host. Free Render services may sleep after idle periods, so the first request can
be slow.

**Option B: Docker Compose with Caddy** ([`compose.yaml`](compose.yaml) and
[`Caddyfile`](Caddyfile))

Use this when you have a VPS or home server and a domain pointing at it:

```bash
git clone https://github.com/Toymen/pure-mpg-mcp.git
cd pure-mpg-mcp
cp .env.example .env
# edit .env and set MCP_DOMAIN=your.domain.example
docker compose up -d --build
```

Your connector URL is:

```text
https://<MCP_DOMAIN>/mcp
```

Open-source PaaS options such as [Coolify](https://coolify.io/),
[Dokku](https://dokku.com/), or [CapRover](https://caprover.com/) can also build
the same `Dockerfile`.

**Option C: Any container host**

Set these environment variables:

```bash
MCP_TRANSPORT=http
HOST=0.0.0.0
PORT=8000
MCP_ALLOWED_HOSTS=your.domain.example
PURE_CONTACT_EMAIL=you@example.org
```

Expose port `8000` behind HTTPS and route requests to `/mcp`.

> **Host allow-list.** The MCP SDK includes DNS-rebinding protection. On hosts
> other than Render, set `MCP_ALLOWED_HOSTS` to the public hostname clients will
> use, without `https://` and without `/mcp`. For multiple hostnames, use a
> comma-separated list.

### From source

Use this for local development or if you want to test unreleased changes:

```bash
git clone https://github.com/Toymen/pure-mpg-mcp.git
cd pure-mpg-mcp
uv pip install -e ".[dev]"
pure-mpg-mcp
```

For HTTP mode from source:

```bash
MCP_TRANSPORT=http PORT=8000 uv run pure-mpg-mcp
```

Then connect a remote-capable MCP client to:

```text
http://localhost:8000/mcp
```

For ChatGPT, use a real HTTPS URL, not `localhost`.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| Client cannot find `uvx` | Install `uv`, then restart the MCP client so it sees the updated `PATH`. |
| Claude Desktop does not show tools | Fully quit and reopen Claude Desktop, then check the JSON config syntax. |
| ChatGPT cannot create the connector | Confirm the `/mcp` URL is public HTTPS and your workspace allows custom MCP apps/connectors. |
| HTTP endpoint returns host/origin errors | Set `MCP_ALLOWED_HOSTS` to the public hostname, for example `mcp.example.org`. |
| Unpaywall is skipped | Set `PURE_CONTACT_EMAIL` to a real non-example email address. |
| First remote request is slow | Free hosting tiers may cold-start after idle periods. |

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `PURE_BASE_URL` | `https://pure.mpg.de/rest` | Override the API base (e.g. a QA instance) |
| `PURE_CONE_URL` | `https://pure.mpg.de/cone` | Override the CONE authority base |
| `PURE_CONTACT_EMAIL` | _(unset)_ | A real contact email. Used for the OpenAlex/Crossref "polite pool", and **required by Unpaywall** — `find_full_text` and `enrich_publication` skip the Unpaywall source (and say so) until this is set. `@example.com` addresses are treated as unset. |
| `MCP_TRANSPORT` | `stdio` | Set to `http` to serve Streamable HTTP at `/mcp` (for remote hosting) instead of stdio. |
| `PORT` / `HOST` | `8000` / `0.0.0.0` | Bind address in HTTP mode (most hosts inject `PORT`). |
| `MCP_ALLOWED_HOSTS` | _(unset)_ | Comma-separated hostnames to trust in HTTP mode (DNS-rebinding protection). Render's hostname is trusted automatically. |

## Example

> "Find recent open-access articles from the Max Planck Institute for Evolutionary Anthropology about Neanderthals, and give me the BibTeX for the top hit."

The agent calls `search_publications(text="Neanderthal", genre="ARTICLE")`,
then `export_publication(item_id, format="BibTex")`.

## Development

```bash
uv pip install -e ".[dev]"
ruff check .
pytest -m "not network"   # offline unit tests (what CI runs)
pytest -m "network and not limit"  # live API smoke tests
PURE_RUN_LIMIT_TESTS=1 pytest -m "network and limit"  # explicit boundary probes
```

Tests are split with `network` and `limit` markers: offline tests cover all the
pure aggregation/parsing logic and run in CI; `network and not limit` checks hit
live public APIs at low volume; `network and limit` probes rate limits and large
result-window boundaries and requires `PURE_RUN_LIMIT_TESTS=1`. GitHub Actions
runs lint + offline tests on Python 3.10 and 3.12
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Live smoke tests run
in a separate scheduled/manual workflow; limit probes are manual-only.

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
3. **Merge the release PR** → the tag and GitHub Release are created. Publish
   the tagged release through the **Publish** workflow
   ([`.github/workflows/publish.yml`](.github/workflows/publish.yml)), which is
   configured for PyPI
   [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no
   stored token).

MCP servers aren't "hosted" on GitHub — GitHub holds the source, PyPI ships the
package (`uvx pure-mpg-mcp`), and clients launch it locally over stdio. For
discovery, the optional **MCP Registry** uses [`server.json`](server.json) as
its manifest; the `<!-- mcp-name: io.github.toymen/pure-mpg-mcp -->` line in
this README verifies ownership. Publish it with the
[`mcp-publisher`](https://modelcontextprotocol.io/registry/quickstart) CLI once
a PyPI release exists.

The PyPI trusted publisher is configured for
[`publish.yml`](.github/workflows/publish.yml) with environment `pypi`. The
workflow can run on a published GitHub Release or manually with a tag ref such
as `pure-mpg-mcp-v0.1.2`.

## API reference

- Swagger UI: <https://pure.mpg.de/rest/swagger-ui/index.html>
- OpenAPI spec: <https://pure.mpg.de/rest/v3/api-docs>
- PubMan REST docs: <https://colab.mpdl.mpg.de/mediawiki/PubMan_REST_API_Documentation>

## License

[MIT](LICENSE). This project is an independent client and is not affiliated with or endorsed by the Max Planck Society / Max Planck Digital Library.
