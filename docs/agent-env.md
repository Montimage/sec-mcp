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

## Build and test commands

- Build the package: `python -m build`
- Run the test suite: `pytest -q -p no:cacheprovider`

## Probe isolation — important

`import sec_mcp` is **not** side-effect free. `sec_mcp/__init__.py` executes
`from .cli import cli`, and `sec_mcp/cli.py` instantiates `core = SecMCP()` at
module level. That constructor creates the SQLite database (plus WAL/SHM
sidecar files) at `MCP_DB_PATH` or the platformdirs default, opens a
`mcp-server.log` file handler under `MCP_LOG_PATH` or the platformdirs
log dir, and starts a background scheduler thread.

Any probe, script, or agent that only wants to inspect the package must first
point the database at a disposable path:

```bash
export MCP_DB_PATH="$(mktemp -d)/probe.db"
python -c "import sec_mcp"
```

Without this, read-only probes write state into the working tree or the user's
default data directory.

## Baseline status

These commands may still be RED — the repository is mid-modernization and the
build/test suite is not yet green. Restoring green is P0. When a command fails,
check it against this known-red baseline before assuming your change caused it.
