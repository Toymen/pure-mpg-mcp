# Changelog

All notable changes to this project are documented here. This file is
maintained automatically by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/); see
[CONTRIBUTING.md](CONTRIBUTING.md).

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
