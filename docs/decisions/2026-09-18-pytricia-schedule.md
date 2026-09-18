# Decision: `pytricia` becomes an optional extra; `schedule` stays

- **Date:** 2026-09-18
- **Status:** accepted
- **Issue:** #45 (plan task 4.7; closes findings `F-DEP-014`, `F-DEP-015`)
- **Deciders:** issue-resolver pipeline (auto mode)

## Context

Two dependency findings were up for decision:

- `pytricia` publishes **sdist only — no wheels** on PyPI (verified for 1.3.0 in
  `uv.lock`: only `pytricia-1.3.0.tar.gz`, no `*.whl` entry). Installing it
  requires a C compiler, so a hard dependency on it made
  `pip install sec-mcp` fail on compiler-less hosts (e.g. slim containers).
- `schedule` has had **no release since 2024-06-18** (1.2.2), raising a
  keep-or-replace maintenance question.

## Decision

### `pytricia` — move to an optional extra (`fast-cidr`)

`pytricia>=1.0.0` moved from `project.dependencies` to
`project.optional-dependencies.fast-cidr`. This is safe because
`sec_mcp/storage_v2.py` **already** treats it as optional at runtime:
`_init_cidr_trees()` wraps `import pytricia` in `try/except ImportError` and
falls back to a pure-Python `ipaddress`-based matcher (`self._cidr_ranges`).
The packaging now matches the code and the README, which already described
pytricia as optional. `pytricia` is also listed in the `dev`
dependency-group so `uv sync` keeps the fast path exercised in development
and CI.

### `schedule` — keep as a required dependency

`schedule>=1.2.0` stays in `project.dependencies`:

- It is **pure Python and ships a wheel** — no compiler problem, so the
  install-time concern that motivated the `pytricia` change does not apply.
- It is deeply embedded: `sec_mcp/update_blacklist.py` imports it at module
  level and drives the daily update thread through `schedule.Scheduler`;
  `sec_mcp/tests/test_scheduler.py` imports it directly. Making it optional
  would push import guards into the package's hot import path
  (`sec_mcp/__init__.py` → `cli` → `SecMCP` → `BlacklistUpdater`).
- Its API surface is tiny, stable, and feature-complete; release inactivity
  since 2024-06-18 is normal for a micro-library of this scope, not
  abandonment evidence affecting us.
- Replacing it (APScheduler, a hand-rolled loop) adds complexity and risk
  for no user-visible gain — the current usage is one daily job and
  `run_pending()` on a daemon thread.

## Consequences

- `pip install sec-mcp` no longer requires a C compiler.
- Users who want fast radix-tree CIDR matching run
  `pip install "sec-mcp[fast-cidr]"` (needs a compiler for the sdist build).
- Without the extra, `HybridStorage` logs "PyTricia not available, using
  fallback CIDR matching (slower)" and CIDR lookups use the `ipaddress`
  fallback — functionally correct, slower on large CIDR sets.
- Revisit `schedule` only if it breaks on a supported Python version or a
  needed fix is blocked upstream.

## Verification

- The issue's preferred check, `docker run --rm python:3.13-slim pip install
  <built wheel>`, could **not** run: the Docker daemon was unavailable on
  the build host at decision time.
- Equivalent evidence gathered instead:
  - `python -m build` succeeds and the wheel `METADATA` lists
    `Requires-Dist: pytricia>=1.0.0; extra == "fast-cidr"` — i.e. pytricia is
    not pulled by a plain install, so no compiler is needed.
  - A clean venv install of the wheel without the extra imports
    `sec_mcp` and exercises the `ipaddress` CIDR fallback end to end.
  - PyPI/`uv.lock` metadata confirms `pytricia` is sdist-only and
    `schedule` ships a `py3-none-any` wheel.
- Baseline-green: the dev dependency-group keeps `pytricia` in the dev
  environment, so the test suite runs against the same configuration as the
  recorded baseline (≥ R).
