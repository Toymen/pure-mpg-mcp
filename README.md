# pure-mpg-mcp

An [MCP](https://modelcontextprotocol.io) server for the **PuRe (PubMan) REST API** — the Max Planck Society's publication repository at [pure.mpg.de](https://pure.mpg.de).

It lets any MCP client (Claude Desktop, Claude Code, etc.) search and retrieve Max Planck publications, organizational units, collections, and feeds.

> **Public & read-only.** This server is anonymous: it only reaches `RELEASED`, publicly visible records. It does **not** log in, write, or access embargoed/private content. The PuRe write/curation/admin endpoints require authorization and are intentionally not exposed.

## Tools

| Tool | What it does |
| --- | --- |
| `search_publications` | Search by free text, author, genre, and year (compact results) |
| `search_raw` | Run a raw Elasticsearch query for advanced cases |
| `get_publication` | Full metadata for one item id (e.g. `item_1552993`) |
| `export_publication` | Export as BibTeX, citation, MARC, EndNote, … |
| `get_file_metadata` | Metadata for an attached file (component) |
| `search_organizations` | Search institutes / departments (organizational units) |
| `list_top_organizations` | Top-level organizational units |
| `search_collections` | Search contexts (collections) |
| `recent_publications` | Feed of recently released items |
| `open_access_feed` | Feed of recent open-access items |
| `service_info` | Version / status of the PuRe instance |

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
