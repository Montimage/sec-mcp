# Changelog

All notable changes to sec-mcp are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- License changed from MIT to Apache License 2.0 (`LICENSE`, `pyproject.toml`,
  README badge/section, `react-landing-page` metadata and copy).

### Added
- Community and docs files: `CODE_OF_CONDUCT.md` (Contributor Covenant),
  GitHub issue templates (bug report, feature request, contact links) and a
  pull-request template; `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`,
  `docs/DEPLOYMENT.md`.
- `SECURITY.md` keeps GitHub private vulnerability reporting as the primary
  channel and adds an email fallback contact.

## [0.5.0] - 2026-09-19

Post-0.4.0 modernization work: MCP SDK 2.x migration, MCP Registry metadata,
storage refactors and a landing-page redesign. Publishing is tag-driven —
pushing `v0.5.0` runs `.github/workflows/pypi-publish.yml`.

### Changed
- `mcp[cli]` migrated to the 2.x SDK (`>=2.2,<3`): `FastMCP` renamed to
  `MCPServer`, tool declarations carry keyword constructors, typed return
  models and annotations.
- v2 storage keeps one in-memory index per entry type instead of tiered
  hot/cold indexes; snapshot swap on reload keeps reads consistent.
- `storage_base.normalize_url` is the single canonicalizer shared by both
  backends — identical verdicts for every URL variant.
- Storage layer split: `storage_base` (shared schema, DB-path resolution,
  `StorageProtocol`), `storage_v2_db` (`SQLiteStore`, all v2 SQLite access),
  `storage_v2_index`, `storage_v2_writes`, `storage_v2_stats`, and the v1
  query half `storage_queries`.
- Feed ingestion split into `feed_parsers` — one parser per source, no
  function-local imports.
- `SecMCP.get_status`/`check_batch` and the MCP `get_status` tool run their
  reads on one shared connection; entry sampling and caches are bounded.
- MCP tools declare annotations, structured `outputSchema`/`isError`
  semantics, server identity and enriched input schemas; `server.json`
  ships MCP Registry metadata with a `uvx` client config.
- No blocking I/O on the MCP event loop.
- `react-landing-page`: tailwindcss 3→4, content synced with the real
  server, nav fixes.
- Test suite fully green (400 passed — the earlier 32/64 known-RED
  `:memory:` failures were retargeted to real databases); CI enforces
  `--cov-fail-under=98` and tests are excluded from the wheel.

### Fixed
- `update_blacklists` is rate limited to one forced update per
  `min_update_interval_seconds` (default 300): a second call inside the
  window returns `{"updated": false, "reason": ...}` and starts no downloads.
  With a progress token the tool emits one `notifications/progress` per source.
- `scheduler_alive` in `get_status` and `get_diagnostics` now reports the real
  scheduler thread state instead of a hardcoded `true`.
- `validate_input` accepts IPv6 literals — bare, bracketed (`[::1]`) and as
  `http://` URL hosts — not just IPv4.
- Domain removal is case-insensitive in both storages (v1 `remove_entry`,
  v2 `SQLiteStore.delete_entry`), matching the lowercase lookup index.
- v2 `add_ip` persistence failure rolls back the in-memory CIDR matcher
  entry too, so a failed write can't keep matching member IPs.
- `update_time` and `log_level` from `config.json` now drive the daily
  scheduled update and startup logging; unused `db_path` key removed.
- Dead code removed: duplicate `SecMCP.check_batch`, unused
  `BlacklistUpdater._is_domain_blacklisted`, unused config load in
  `SecMCP.__init__`. `E722`/`BLE001`/`F811` are enabled and clean.

## [0.4.0] - 2026-09-19

First 0.x release carrying the modernization sprint. Publishing is tag-driven:
pushing `v0.4.0` runs `.github/workflows/pypi-publish.yml`, which verifies the
tag matches `pyproject.toml`, builds, lints, gates on the test baseline, then
publishes to PyPI (token auth via `PYPI_API_TOKEN`).

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
