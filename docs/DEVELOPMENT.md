# Development

A thin hub — the detailed commands live in the linked files rather than being
duplicated here.

## Quick links

- **Dev setup, test/lint/coverage commands, branch/commit/PR conventions:**
  [../CONTRIBUTING.md](../CONTRIBUTING.md) — `uv sync` is the single
  dev-install command; `uv.lock` is authoritative.
- **Toolchain, environment variables, probe isolation:**
  [agent-env.md](agent-env.md) — read before running ad-hoc Python;
  constructing `SecMCP()`/`Storage`/`BlacklistUpdater` writes a DB, opens a
  log handler and starts a scheduler thread unless you redirect `MCP_DB_PATH`
  and set `MCP_DISABLE_SCHEDULER=1`.
- **Design overview:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Release/deploy:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Community standards:** [../CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md),
  [../SECURITY.md](../SECURITY.md)

## Repo layout

| Path | What it is |
|------|------------|
| `sec_mcp/` | The package; `config.json` is shipped package data |
| `sec_mcp/tests/` | pytest suite — `pytest.ini` sets `testpaths`; `conftest.py` makes runs hermetic (temp `MCP_DB_PATH`/`MCP_LOG_PATH`/`MCP_CACHE_DIR`, scheduler off) |
| `react-landing-page/` | Standalone Vite/React site with its own `package.json` — not part of the Python package |
| `scripts/check_test_baseline.sh` | Recorded pass floor used by CI and pre-commit |
| `docs/` | This file, `agent-env.md`, `decisions/` (ADRs), `archive/` (historical PRD/tasks) |

## CI gates

`.github/workflows/ci.yml` runs on every push to `main` and every PR:
build → `ruff check` → `check_test_baseline.sh` →
`pytest --cov-fail-under=98`, on Python 3.11–3.14 (`UV_PYTHON` pins the
matrix interpreter past `.python-version`). A second job builds
`react-landing-page` (`npm ci && npm run build`, Node 24) on PRs.
`.pre-commit-config.yaml` mirrors the ruff and baseline gates locally.

## Conventions (summary — details in CONTRIBUTING.md)

- Branch `<type>/<issue>-<slug>`; Conventional Commits with an issue ref;
  squash-merge, `Closes #<issue>` on the first line of the PR body.
- Suite is fully green (400 tests); the 32/64 baseline script is a floor, not
  the bar — do not merge a regression.
- Design decisions worth recording go in `docs/decisions/` as dated ADRs.
