# Decision: coverage measured in CI; M3 target set to 98%

- **Date:** 2026-09-19
- **Status:** accepted
- **Issue:** #46 (plan task 5.1; closes finding `F-TEST-007`)
- **Deciders:** issue-resolver pipeline (auto mode)

## Context

Plan task 5.1 (Sprint 5, Phase P3 "Clean & Harden") requires measuring test
coverage before improving it — coverage was "Not Assessed" — and binding the
result to milestone M3 as `max(60, measured + 20)`. The task's M3 row lives in
`MODERNIZATION_PLAN.md`, which is an **untracked user file** and was absent
from the working tree at decision time, so the target is recorded here and in
the closing PR body instead of being written into that plan row.

## Measured

`uv run pytest --cov=sec_mcp --cov-report=term -q -p no:cacheprovider` on
`main` (256aa9d):

- **TOTAL: 3621 statements, 799 missed → 78%**
- Suite result unchanged with `--cov` enabled: 155 passed / 32 failed — the
  known-RED baseline (≥ R) still holds; coverage plugins do not perturb it.

## Decision

- **M3 coverage target = max(60, 78 + 20) = 98%.**
- CI reports the number on every run: an informational
  `uv run pytest --cov=sec_mcp --cov-report=term -q -p no:cacheprovider`
  step follows the baseline gate in `.github/workflows/ci.yml`. It is
  deliberately non-gating (`|| true`): the suite is known-RED and exits 1,
  and a genuine suite crash is already caught by the baseline gate.
  `pytest-cov>=4.0.0` was already in the `dev` dependency-group.
- Wheel hygiene: `sec_mcp/tests/` was discovered as a *namespace* package
  (`[tool.setuptools.packages.find]` defaults `namespaces=true` under
  pyproject, so the missing `__init__.py` did not protect it) and shipped 15
  files in the wheel. Three packaging changes keep it out while preserving
  sdist parity:
  - `exclude = ["sec_mcp.tests*"]` stops namespace-package discovery.
  - `MANIFEST.in` (`recursive-include sec_mcp/tests *.py`) grafts the suite
    back into the **sdist** so downstream packagers can still run it.
  - `[tool.setuptools] include-package-data = false` is required because
    pyproject configures it `true` by default — without it, files grafted
    into the sdist manifest ride into the wheel as `sec_mcp` package data.
    `config.json` still ships via the explicit `[tool.setuptools.package-data]`
    table.
  `python -m zipfile -l dist/*.whl | grep -c "tests/"` now reports **0**.

## Consequences

- Every CI run prints a coverage table; tracking progress toward the 98% M3
  target only requires reading the log, no local setup.
- The installed wheel no longer carries the pytest suite: smaller artifact,
  no `sec_mcp.tests` import surface for end users.
- When `MODERNIZATION_PLAN.md` is available again, its M3 row should be
  updated to **98%** (measured 78% + 20).

## Verification

- `python -m zipfile -l dist/*.whl | grep -c "tests/"` → `0` (was `15`).
- `./scripts/check_test_baseline.sh` → `OK` at or above baseline R.
- Coverage command exits 1 (known-RED) but prints `TOTAL … 78%`.
