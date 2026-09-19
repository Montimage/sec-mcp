Closes #<issue>

## What

<!-- What this PR changes and why. Keep it scoped to the issue. -->

## Checklist

- [ ] `uv run ruff check .` is clean
- [ ] `uv run pytest -q -p no:cacheprovider` passes (suite is fully green)
- [ ] Coverage gate holds: `--cov-fail-under=98`
- [ ] New behavior has a test
- [ ] `CHANGELOG.md` updated under `## [Unreleased]` for user-facing changes
- [ ] No secrets, `.env`, credentials, SQLite DBs or `*.db-shm`/`*.db-wal` sidecars committed
