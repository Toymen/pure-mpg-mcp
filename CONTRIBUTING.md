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

Common types and how they affect the version (pre-1.0, so bumps stay conservative):

| Type | Changelog section | Version effect (0.x) |
| --- | --- | --- |
| `feat:` | Features | patch bump (e.g. 0.1.0 → 0.1.1) |
| `fix:` | Bug Fixes | patch bump |
| `perf:` | Performance | patch bump |
| `docs:` | Documentation | patch bump |
| `refactor:` | Refactoring | patch bump |
| `deps:` | Dependencies | patch bump |
| `build:` | Build System | patch bump |
| `ci:`, `test:`, `chore:` | hidden | no release |

A breaking change — `feat!:` or a `BREAKING CHANGE:` footer — bumps the minor
version while the project is pre-1.0, and the major version once it reaches 1.0.

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
