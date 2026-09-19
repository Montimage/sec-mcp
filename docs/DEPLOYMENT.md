# Deployment

Three deploy surfaces: the PyPI package, the end-user MCP server, and the
GitHub Pages landing site.

## PyPI release (maintainers)

Releases are tag-driven:

1. Bump `version` in `pyproject.toml` — and `version` / `packages[].version`
   in `server.json` (MCP Registry metadata; `sec_mcp/tests/test_server_json.py`
   guards the match).
2. Merge to `main`, then push a `v<version>` tag.

`.github/workflows/pypi-publish.yml` triggers on `v*.*.*` tags and runs:

- verify tag == `pyproject.toml` version,
- `uv sync --frozen`, `python -m build`, `ruff check`,
  `scripts/check_test_baseline.sh`,
- upload `dist/` to PyPI via `pypa/gh-action-pypi-publish` using the
  `PYPI_API_TOKEN` secret — token auth, no trusted publisher is registered
  for this repo's OIDC claims (see the comment in the workflow).

## End-user deployment (MCP server / CLI)

The published package provides two console scripts
(`pyproject.toml` `[project.scripts]`):

- `sec-mcp` — CLI (`sec_mcp.cli:cli`)
- `sec-mcp-server` — MCP server over **stdio only** (`sec_mcp.start_server:main`)

Install and first-run:

```bash
pip install sec-mcp        # or: uvx --from sec-mcp sec-mcp update
sec-mcp update             # download + index the feeds — required once
```

MCP client configuration (Claude Desktop, Cursor, Windsurf, …):

```json
{
  "mcpServers": {
    "sec-mcp": {
      "command": "uvx",
      "args": ["--from", "sec-mcp", "sec-mcp-server"],
      "env": { "MCP_USE_V2_STORAGE": "true" }
    }
  }
}
```

`server.json` at the repo root ships the matching MCP Registry entry
(`io.github.montimage/sec-mcp`, registry type `pypi`, `runtimeHint: uvx`,
stdio transport).

Production-relevant environment variables (full reference:
[agent-env.md](agent-env.md)):

| Variable | Use |
|----------|-----|
| `MCP_DB_PATH` | Pin the SQLite location (default: platformdirs user data dir) |
| `MCP_USE_V2_STORAGE` | `true` selects the in-memory `HybridStorage` backend |
| `MCP_LOG_PATH` | Log file location (default: platformdirs log dir) |
| `MCP_CACHE_DIR` | Feed download cache (default: platformdirs cache dir) |
| `MCP_DISABLE_SCHEDULER` | `1` disables the daily-update thread for embedded/one-shot use |

## Landing page (GitHub Pages)

`react-landing-page/` is a standalone Vite/React site.
`.github/workflows/deploy-landing-page.yml` deploys it:

- **Trigger:** push to `main`/`master` touching `react-landing-page/**`, or
  `workflow_dispatch`.
- **Build:** Node 24, `npm ci`, `npm run build` (Vite build + SSR prerender).
- **Deploy:** `actions/configure-pages` → `upload-pages-artifact` →
  `actions/deploy-pages` to <https://montimage.github.io/sec-mcp/>; one
  concurrent deployment (`concurrency: pages`).

## Operational notes

- Feeds are downloaded over **HTTPS only** (non-HTTPS sources are rejected),
  bounded by `max_feed_bytes`, and sanity-checked against
  `min_feed_entries`/`max_feed_entries` — a failing feed keeps existing data.
  `max_range_addresses` caps expanded CIDR ranges. All bounds live in
  `sec_mcp/config.json`.
- `update_blacklists`/`sec-mcp update` is rate limited to one forced update
  per `min_update_interval_seconds` (default 300); the scheduled daily update
  runs at `update_time`.
- One source's failure is logged and skipped — it never aborts the remaining
  feeds.
- Log/cache/database locations default to platformdirs paths and are
  overridable per environment (table above).
