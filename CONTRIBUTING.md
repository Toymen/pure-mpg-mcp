# Contributing

## Conventional Commits → automatic versioning

This repo versions itself automatically with
[release-please](https://github.com/googleapis/release-please). It reads commit
messages, so they must follow the
[Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Only `feat`, `fix`, and breaking changes trigger a release. Other types show up
in the changelog of the next release (unless hidden) but don't cut a release on
their own. Pre-1.0, bumps stay conservative:

| Type | Changelog section | Triggers release? | Version effect (0.x) |
| --- | --- | --- | --- |
| `feat:` | Features | yes | patch bump (e.g. 0.1.0 → 0.1.1) |
| `fix:` | Bug Fixes | yes | patch bump |
| `feat!:` / `BREAKING CHANGE:` | — | yes | minor bump (major once ≥ 1.0) |
| `perf:` | Performance | no | included if a release is cut |
| `docs:` | Documentation | no | included if a release is cut |
| `refactor:` | Refactoring | no | included if a release is cut |
| `deps:` | Dependencies | no | included if a release is cut |
| `build:` | Build System | no | included if a release is cut |
| `ci:`, `test:`, `chore:` | hidden | no | — |

Examples:

```
feat: add ORCID-based author enrichment tool
fix: handle missing DOI in find_full_text
docs: document PURE_CONTACT_EMAIL for Unpaywall
feat!: rename analyze_authors output fields
```

## Release flow

1. Land Conventional Commits on `main`.
2. release-please keeps a **release PR** open with the next version and an
   updated `CHANGELOG.md`. It bumps the version in `pyproject.toml`,
   `src/pure_mpg_mcp/__init__.py`, and `server.json` together.
3. Merge the release PR → the tag and GitHub Release are created → the package
   is built and published to PyPI via Trusted Publishing. No manual tagging.

## Development

```bash
uv pip install -e ".[dev]"
ruff check .
pytest -m "not network"   # offline unit tests (what CI runs)
pytest                     # include live API smoke tests
```
