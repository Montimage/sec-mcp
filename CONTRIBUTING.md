# Contributing to sec-mcp

Thanks for helping improve sec-mcp. This file covers the dev setup, the test
and lint commands CI enforces, and the branch/commit/PR conventions used in
this repository.

## Dev setup

Requires **Python ≥3.11** and [uv](https://docs.astral.sh/uv/getting-started/installation/)
(`pip install uv` if needed).

```bash
git clone https://github.com/montimage/sec-mcp.git
cd sec-mcp
uv sync
```

`uv sync` is the single dev-install command: it creates `.venv`, installs the
package editable, and adds the dev dependency group (pytest, pytest-asyncio,
pytest-cov, ruff, pytricia) pinned by `uv.lock`. The repo's `.python-version`
pins the interpreter to 3.11; pass `uv sync --python 3.13` to develop against
a different one.

No uv? The equivalent is `pip install -e .` plus `pip install pytest
pytest-asyncio pytest-cov ruff` — but the lockfile (`uv.lock`) is
authoritative, so prefer `uv sync`.

Optional: `pre-commit install` wires the local hooks (`ruff check` + the
pytest baseline script) into every commit.

## Running tests

```bash
# Full suite — fully green at 400 tests
uv run pytest -q -p no:cacheprovider

# Single file while iterating
uv run pytest -q -p no:cacheprovider sec_mcp/tests/test_storage.py

# Lint
uv run ruff check .

# Coverage (CI enforces this gate)
uv run pytest --cov=sec_mcp --cov-report=term --cov-fail-under=98 -q -p no:cacheprovider

# Recorded-baseline floor
./scripts/check_test_baseline.sh
```

The suite is hermetic: `sec_mcp/tests/conftest.py` redirects `MCP_DB_PATH`,
`MCP_LOG_PATH` and `MCP_CACHE_DIR` to temp dirs, gives each test a private
working directory, and disables the scheduler — a test run leaves no trace in
the repo or your home directory.

**Probe isolation:** that hermeticity does not extend to ad-hoc Python you run
yourself. Importing `sec_mcp` is side-effect free, but *constructing*
`SecMCP()`, `Storage`/`HybridStorage`, or `BlacklistUpdater` writes a SQLite
DB (+WAL/SHM sidecars), opens a log handler and starts a scheduler thread.
Before probing, redirect the artifacts:

```bash
export MCP_DB_PATH="$(mktemp -d)/probe.db"
export MCP_DISABLE_SCHEDULER=1   # if you don't want the background thread
```

Full env-var reference: `docs/agent-env.md`.

## Baseline expectations

- The suite is **fully green** (400 passed, 0 failed). Do not merge work that
  introduces a failure — `scripts/check_test_baseline.sh` keeps the old
  32/64 floor as a hard stop, but the real bar is no regressions.
- Coverage must stay ≥98% (`--cov-fail-under=98` in CI).
- `uv run ruff check .` must stay clean (rules: `F`, `I`, `ASYNC`, `E722`,
  `BLE001`; see `pyproject.toml`).
- New behavior gets a test. Minimal diffs — don't refactor outside the
  issue's scope.
- CI runs the suite on Python 3.11, 3.12, 3.13 and 3.14; it also builds the
  landing page on PRs that touch `react-landing-page/`.

## Branch and commit conventions

- **Branch:** `<type>/<issue>-<slug>` — e.g. `fix/42-mobile-auth-redirect`,
  `docs/23-update-api-reference`. Types: `fix`, `feat`, `refactor`, `docs`,
  `test`, `chore`.
- **Commit:** `<type>(<scope>): <description> (#<issue>)` — Conventional
  Commits, imperative mood, issue reference required, first line ≤72 chars.
- **PR title:** same format as commits; put `Closes #<issue>` on the first
  line of the body so merge auto-closes the issue.
- Don't commit or push to `main` directly — always through a PR.
- Never commit secrets, `.env`, credentials, SQLite DBs or `*.db-shm`/`*.db-wal`
  sidecars.

## PR process

1. Fork the repo (or branch directly if you have write access) and create
   your branch from `main`.
2. Make the change; keep it scoped to the issue.
3. Run the suite + lint locally; keep them green.
4. Push and open the PR. CI runs build → ruff → baseline → coverage on all
   four Python versions.
5. Address review feedback with follow-up commits (`fix(<scope>): address
   review feedback (#<issue>)`).
6. Maintainers squash-merge; the PR title/body become the commit message —
   keep them accurate.
7. Notable user-facing changes get a `CHANGELOG.md` entry under
   `## [Unreleased]` (the file follows Keep a Changelog).

## Releasing (maintainers)

Releases are tag-driven: bump `version` in `pyproject.toml`, merge, then push
a `v<version>` tag. `.github/workflows/pypi-publish.yml` verifies the tag,
builds, lints, runs the baseline gate and publishes to PyPI.

## Reporting issues and security problems

- Bugs and feature requests: [GitHub Issues](https://github.com/Montimage/sec-mcp/issues).
- Security vulnerabilities: follow [SECURITY.md](SECURITY.md) — do not open
  a public issue.
