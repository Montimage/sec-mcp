# Changelog

All notable changes to sec-mcp are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — pending release

First 0.x release carrying the modernization sprint. Publishing is tag-driven:
pushing `v0.4.0` runs `.github/workflows/pypi-publish.yml`, which verifies the
tag matches `pyproject.toml`, builds, lints, gates on the test baseline, then
publishes to PyPI via trusted OIDC publishing.

### Security
- Pin `mcp[cli]>=1.28.1,<2` — bounds the previously unbounded
  `mcp[cli]>=0.1.0` requirement so `import sec_mcp.mcp_server` resolves against
  the 1.x API the server is written for.
- Advisory floors on transitive dependencies (uv constraints): `h11>=0.16.0`,
  `starlette>=1.3.1`, `pygments>=2.20.0`, `python-dotenv>=1.2.2`.
- HTTPS-only blacklist feed downloads with bounded size, entry sanity checks
  and atomic file swap.
- Storage fails closed on unreadable databases — no silent v2→v1 fallback.
- `SECURITY.md` and Dependabot configuration added.

### Changed
- Packaging consolidated into `pyproject.toml` (setuptools backend); the
  package version is single-sourced there and exposed via
  `sec_mcp.__version__`.
- `pytricia` is now an opt-in extra: `pip install "sec-mcp[fast-cidr]"`.
  Without it, storage falls back to a pure-Python `ipaddress` CIDR matcher.
- Dropped unused `requests` and `tqdm`; declared `platformdirs` and
  `click>=8.3.3`; bounded `idna<3.20`.
- `import sec_mcp`, `sec_mcp.cli` and `sec_mcp.mcp_server` are side-effect
  free — `SecMCP()` is constructed lazily on first use.
- CI matrix Python 3.11–3.14; GitHub Actions pinned to SHA; Node.js 24 LTS for
  the landing page.

### Fixed
- `update_blacklists` is rate limited to one forced update per
  `min_update_interval_seconds` (default 300): a second call inside the
  window returns `{"updated": false, "reason": ...}` and starts no downloads.
  With a progress token the tool emits one `notifications/progress` per source.
- `scheduler_alive` in `get_status` and `get_diagnostics` now reports the real
  scheduler thread state instead of a hardcoded `true`.
- MCP admin tool input validation; v1 `remove_entry` repaired against real
  tables; single owned scheduler job with awaited updates and idempotent
  stop; valid JSON for `--json` CLI checks; platformdirs log/cache dirs with
  a single owned handler; Dshield ranges stored as CIDR networks.

### Added
- Tiered hot/cold lookup system, URL normalization, integer-based IPv4
  storage and enhanced metrics (v2 storage, `MCP_USE_V2_STORAGE=true`).
- Hermetic test suite with recorded baseline (`R = 32/64`,
  `scripts/check_test_baseline.sh`) and characterization tests for all six
  MCP tools.

Earlier development history (0.1.x–0.3.x, unpublished 0.4.0 storage work) is
archived under `dev-docs/` (not tracked).
