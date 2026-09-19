# AGENTS.md

## Project
sec-mcp — Python library + CLI (and MCP server) that checks domains, URLs and
IPs against security blacklists backed by SQLite. `react-landing-page/` is a
standalone Vite site, not part of the package. `import sec_mcp` is side-effect
free — constructing `SecMCP()` is what creates the database, log file and
scheduler thread (see `docs/agent-env.md`).

## Commands
- Build/test/env commands → `docs/agent-env.md` (single source; also named in
  `CLAUDE.md` — do not restate them here)
- Package manager: `uv` — `pyproject.toml` + `uv.lock` are authoritative;
  legacy `setup.py`/`requirements.txt` still exist
- Python ≥ 3.11 required

## Layout
- `sec_mcp/` — the package; `config.json` is shipped package data
- `sec_mcp/tests/` — pytest suite (`pytest.ini` sets `testpaths`)
- `react-landing-page/` — standalone Vite/React site with its own `package.json`
- `docs/` — project docs, incl. `agent-env.md`

## Conventions
- Minimal diffs; don't refactor beyond the issue's scope
- Branch: `<type>/<issue>-<slug>` (e.g. `docs/23-update-api-reference`)
- Commit: `<type>(<scope>): <description> (#<issue>)` — issue ref required

## Constraints
- Don't commit or push to `main` unless asked
- Never commit secrets, `.env`, credentials, SQLite DBs or `*.db-shm`/`*.db-wal` sidecars
- Export `MCP_DB_PATH` to a temp path before constructing `SecMCP()` in
  probes — construction writes a DB, log file and scheduler thread
  (see `docs/agent-env.md`)

## Done when
- Build + suite green using the commands in `docs/agent-env.md` — the suite is
  fully green since #55; a change is done when it keeps it green and holds the
  `--cov-fail-under=98` CI coverage gate
- New behavior has a test

## Read when needed
- Environment, env vars, probe isolation → `docs/agent-env.md`
- Historical (archived) PRD / task plan → `docs/archive/`

## Token Efficiency
- Never re-read files you just wrote or edited. You know the contents.
- Never re-run commands to "verify" unless the outcome was uncertain.
- Don't echo back large blocks of code or file contents unless asked.
- Batch related edits into single operations. Don't make 5 edits when 1 handles it.
- Skip confirmations like "I'll continue..." Just do it.
- If a task needs 1 tool call, don't use 3. Plan before acting.
- Do not summarize what you just did unless the result is ambiguous or you need additional input.
