# Changelog

All notable changes to this project are documented here. This file is
maintained automatically by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/); see
[CONTRIBUTING.md](CONTRIBUTING.md).

## [0.1.1](https://github.com/Toymen/pure-mpg-mcp/compare/pure-mpg-mcp-v0.1.0...pure-mpg-mcp-v0.1.1) (2026-07-07)


### Features

* fill anonymous API gaps and cover the full advanced-search field set ([2e29013](https://github.com/Toymen/pure-mpg-mcp/commit/2e29013d5229026d338492e60f39fff55d781fde))
* support remote hosting via Streamable HTTP for a connector URL ([8c4f0b2](https://github.com/Toymen/pure-mpg-mcp/commit/8c4f0b23fa4a2fe8377aa8672dde52d1e383b23a))


### Bug Fixes

* revert unverified 10k pagination cap; add live CONE language vocabulary ([8209b51](https://github.com/Toymen/pure-mpg-mcp/commit/8209b51a0de322f2266c2ec98547eafe60b06fdf))
* switch fetch_all to search_after to bypass 1000-record scroll cap ([74a4094](https://github.com/Toymen/pure-mpg-mcp/commit/74a4094f6a0463db56b800e01ebb359c7c666953))
* trust deployment host in HTTP mode so remote connector works ([599502f](https://github.com/Toymen/pure-mpg-mcp/commit/599502fa70ea2423cbe399d7a219b1a8b9967f59))


### Documentation

* add Use-with-Claude install guide and PyPI badge ([f4a7b68](https://github.com/Toymen/pure-mpg-mcp/commit/f4a7b68cf8d99dca3e2062ec6e4abd7a72a88d4d))

## 0.1.0 (2026-06-08)

Initial release.

### Features

- Search and retrieve Max Planck Society publications via the public PuRe
  (PubMan) REST API — anonymous, read-only (`search_publications`, `search_raw`,
  `get_publication`, `find_by_doi`, `export_publication`, `get_file_metadata`).
- Organizational units, collections, and feeds (`search_organizations`,
  `list_top_organizations`, `search_collections`, `recent_publications`,
  `open_access_feed`, `service_info`).
- Bibliometric analysis: `publication_statistics`, `coauthorship_analysis`,
  and `analyze_authors` (CONE authority resolution for full names, ORCID,
  affiliation).
- External enrichment keyed on PuRe DOIs: `enrich_publication`,
  `get_citation_metrics`, `find_full_text` — backed by OpenAlex, Crossref,
  Unpaywall, and Semantic Scholar.
