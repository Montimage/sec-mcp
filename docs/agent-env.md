# Agent environment notes

Single source for the toolchain, environment variables, and build/test commands
for this repository. Read this before running anything — including read-only
probes, which are not side-effect free here (see *Probe isolation*).

## Toolchain

- **Python 3.11 or newer** — `pyproject.toml` sets `requires-python = ">=3.11"`.
- **uv** — package and lockfile management; `uv.lock` is the authoritative lockfile.
- **Node.js 24 LTS + npm** — required only for `react-landing-page/` (Vite + React;
  see `react-landing-page/package.json` and `react-landing-page/.nvmrc`). Not
  needed for the core `sec_mcp` package.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `MCP_DB_PATH` | SQLite database path used by `sec_mcp/storage.py` (v1) and `sec_mcp/storage_v2.py` (v2) when no explicit path is passed. |
| `MCP_USE_V2_STORAGE` | Storage backend selector in `create_storage()`: `true` enables `HybridStorage` (v2); any other value (or unset) uses legacy `Storage` (v1). |
| `MCP_LOG_PATH` | Log file path for `setup_logging()`; default is `platformdirs.user_log_dir("sec-mcp", "montimage")/mcp-server.log`. |
| `MCP_CACHE_DIR` | Feed cache directory used by the blacklist updater; default is `platformdirs.user_cache_dir("sec-mcp", "montimage")`. |
| `SEC_MCP_CORS_ORIGINS` | CORS origins (comma-separated) for `sec-mcp-server --http`, read at app build time in `sec_mcp/http_transport.py`; default is the local Vite ports 3000/4173 plus `https://montimage.github.io`; `*` allows any origin and disables DNS-rebinding protection. |
| `SEC_MCP_HTTP_AUTH_TOKEN` | Optional bearer token that `sec-mcp-server --http` requires on every request. |

## Build and test commands

- Build the package: `python -m build`
- Run the test suite: `pytest -q -p no:cacheprovider`

## Probe isolation — important

`import sec_mcp`, `import sec_mcp.cli` and `import sec_mcp.mcp_server` are
side-effect free: they create no database, open no log file and start no
scheduler thread. The shared `core` instance behind each entry-point module is
built lazily by `get_core()` on first use — when a CLI command runs, when an
MCP tool is invoked, or eagerly in `start_server.main()`.

Constructing `SecMCP()`, `Storage`/`HybridStorage`, or `BlacklistUpdater` is
**not** side-effect free: it creates the SQLite database (plus WAL/SHM
sidecar files) at `MCP_DB_PATH` or the platformdirs default, opens a
`mcp-server.log` file handler under `MCP_LOG_PATH` or the platformdirs
log dir, and starts a background scheduler thread (unless
`MCP_DISABLE_SCHEDULER=1`).

Any probe, script, or agent that constructs these objects must first point the
database at a disposable path:

```bash
export MCP_DB_PATH="$(mktemp -d)/probe.db"
python -c "import sec_mcp; sec_mcp.SecMCP()"
```

Without this, probes that touch storage write state into the working tree or
the user's default data directory.

## Baseline status

The build and suite are **fully green** (400 passed, 0 failed — the earlier
32/64 known-RED era ended with issue #55). CI enforces the suite on Python
3.11–3.14 plus `--cov-fail-under=98`. `scripts/check_test_baseline.sh` still
carries the recorded 32/64 floor as a hard stop, but the working bar is no
regressions: when a command fails, assume your change caused it and check the
diff before looking elsewhere.
