# Step 3a — Documentation Plan

**Repo:** `/Users/montimage/workspace/montimage/sec-mcp` (`Montimage/sec-mcp`, public)
**Basis:** `.oss-ready/01-audit.md` (32/39, verdict PARTIAL), codebase read on `main` @ v0.5.0
**Project profile:** Python ≥3.11 library + Click CLI + MCP server (stdio), SQLite-backed
blacklist storage with v1/v2 backends; uv-managed (`uv.lock` authoritative); pytest suite
(~400 tests, `--cov-fail-under=98`); setuptools build; CI on py3.11–3.14; tag-driven PyPI
publish; `react-landing-page/` is a standalone Vite site deployed to GitHub Pages.

**License decision (user-confirmed):** switch MIT → **Apache-2.0**. The skill asset only
ships `assets/LICENSE-MIT` — there is NO Apache template in
`/Users/montimage/.agents/skills/oss-ready/assets/`. The Apache-2.0 text must be fetched
from the canonical source (`https://www.apache.org/licenses/LICENSE-2.0.txt`, verbatim,
no copyright substitution in the body — the APPENDIX boilerplate stays as-is) or written
fresh. Every file touching "MIT" must be updated in the same PR (list below).

**Template sourcing rule:** `CODE_OF_CONDUCT.md`, `SECURITY.md` (if used),
`.github/ISSUE_TEMPLATE/*` and `PULL_REQUEST_TEMPLATE.md` exist in
`/Users/montimage/.agents/skills/oss-ready/assets/` and must be installed with `cp`
(binary-safe copy), not read+rewritten — then placeholders filled via `edit`.

---

## File plan

| # | Path | Action | Rationale |
|---|------|--------|-----------|
| 1 | `LICENSE` | **update** (replace text) | User-chosen switch MIT → Apache-2.0; fetch canonical text (no asset template). Keep a copyright line: decide holder (`Luong NGUYEN` vs `Montimage`) and year. |
| 2 | `pyproject.toml` | **update** | `license = "MIT"` → `"Apache-2.0"` (L10). Optional: add `License :: OSI Approved :: Apache Software License` classifier. |
| 3 | `README.md` | **update** | MIT badge (L13) → Apache-2.0 badge; License section (L504–506) → Apache-2.0; add links to new `docs/` files + CODE_OF_CONDUCT in Contributing section. Content otherwise complete (audit S2 8/8). |
| 4 | `CODE_OF_CONDUCT.md` | **create** | Missing (S1). `cp assets/CODE_OF_CONDUCT.md` (Contributor Covenant 2.0), fill `[INSERT CONTACT METHOD]` — needs contact decision (see Q1). |
| 5 | `SECURITY.md` | **update** | Exists and is good, but routes reports to GitHub private vulnerability reporting which is **disabled** on the repo. Plan covers both fixes: (a) reword "How to Report" to make email the working channel and mark the advisories URL as "if enabled"; (b) flag enabling PVR in repo Settings as a manual step. Do NOT `cp` the asset over it — skill edge-case rule: never replace user content; edit only the reporting section. |
| 6 | `.github/ISSUE_TEMPLATE/bug_report.md` | **create** | Missing (S3). `cp` from assets; tailor "Environment" field to Python version + `sec-mcp --version`. |
| 7 | `.github/ISSUE_TEMPLATE/feature_request.md` | **create** | Missing (S3). `cp` from assets, unchanged. |
| 8 | `.github/PULL_REQUEST_TEMPLATE.md` | **create** | Missing (S3). `cp` from assets; align with repo conventions — `Closes #<issue>` first line (CONTRIBUTING L88-89), checklist adds `ruff check` clean, suite green, coverage ≥98%, CHANGELOG entry for user-facing changes. |
| 9 | `.github/ISSUE_TEMPLATE/config.yml` | **create** (optional) | Small win: `contact_links` pointing security reports to SECURITY.md and general help to the Montimage profile; prevents blank issues pointing at the wrong channel. |
| 10 | `docs/ARCHITECTURE.md` | **create** | Missing (S4); real gap — v1/v2 storage split, lazy core, feed pipeline, MCP tool layer deserve a design doc. Outline below. |
| 11 | `docs/DEVELOPMENT.md` | **create** | Missing (S4), but content already lives in CONTRIBUTING.md + `docs/agent-env.md`. Thin hub doc — do not duplicate commands. Outline below. |
| 12 | `docs/DEPLOYMENT.md` | **create** | Missing (S4). Covers three real deploy surfaces: PyPI release flow, end-user MCP-server deployment (uvx/stdio), landing-page Pages deploy. Outline below. |
| 13 | `react-landing-page/package.json` | **update** | `"license": "MIT"` → `"Apache-2.0"` (same repo → same license; confirm Q3). |
| 14 | `react-landing-page/README.md` | **update** | L95 "licensed under MIT" → Apache-2.0. |
| 15 | `react-landing-page/public/index.md` | **update** | L3 "MIT license" → Apache-2.0 (landing-page copy). |
| 16 | `CHANGELOG.md` | **update** (minor) | Keep at root (audit accepted alt. location). Add `## [Unreleased]` entries for license change + new community files when the docs PR lands. |
| 17 | `CONTRIBUTING.md` | **update** (minor) | Content complete (audit S1). One-line addition: link `CODE_OF_CONDUCT.md` in the header/"Reporting issues" section. |
| 18 | `docs/CHANGELOG.md` | **skip** | Root `CHANGELOG.md` already satisfies the checklist (Keep a Changelog, through 0.5.0, linked from README/CONTRIBUTING). A second file would fork the source of truth. |
| 19 | `docs/USER_GUIDE.md` | **skip** | README already covers install, quick start, CLI, Python API, MCP server, config, benchmarking (532 lines, audit 8/8); `docs/playbook.md` is the usage cookbook. Would duplicate. |
| 20 | `docs/API.md` | **skip** | Public API is tiny and fully documented in README + docstrings: `SecMCP`, `CheckResult`, `StatusInfo` (`sec_mcp/__init__.py`), 8 CLI commands, 6 MCP tools with typed output schemas. Fold any extra detail into ARCHITECTURE.md. |
| 21 | `SECURITY.md` via asset template | **skip** | Asset exists but current repo file is richer (supported-versions table, fallback channel); per skill edge-case rule, edit in place — do not `cp` over it. |
| 22 | `AGENTS.md`, `CLAUDE.md`, `docs/agent-env.md`, `docs/playbook.md`, `docs/decisions/`, `docs/archive/` | **keep** | Accurate and current; new docs link to them rather than restate. |
| 23 | `.github/workflows/{ci,pypi-publish,deploy-landing-page}.yml`, `.github/dependabot.yml`, `server.json`, `pytest.ini`, `.pre-commit-config.yaml`, `MANIFEST.in` | **keep** | All current; no license fields, no doc drift. (`server.json` has no license key; pytest/MANIFEST unaffected.) |

### Out of scope / do not touch
Untracked files (`.gitissue*`, `CODE_REVIEW.md`, `MODERNIZATION_*.md`,
`react-landing-page/.agent-ready*`), gitignored `dev-docs/`, generated `sec_mcp.egg-info/`.

---

## Outlines for created files

### `docs/ARCHITECTURE.md`
- **Overview** — one paragraph: library/CLI/MCP-server over SQLite blacklist storage; `import sec_mcp` side-effect free, lazy `get_core()` singleton (`cli.py:16`, `mcp_server.py:48`).
- **Component map** — `SecMCP` facade (`sec_mcp.py`: check/check_domain/check_url/check_ip/check_batch/get_status/update/sample, `CheckResult`/`StatusInfo` dataclasses); entry points `sec-mcp`→`cli:cli`, `sec-mcp-server`→`start_server:main` (stdio transport); `BlacklistUpdater` (feed download, `schedule` daily job at `update_time`, `min_update_interval_seconds` rate limit, `MCP_CACHE_DIR` cache); `FeedParser` (one parser per source in `config.json`'s 10 feeds).
- **Storage layer** — `create_storage()` selects on `MCP_USE_V2_STORAGE`; v1 `Storage`/`StorageQueryMixin` (WAL SQLite, LRU positive-hit cache, lazy CIDR list); v2 `HybridStorage` split across `storage_v2{,_db,_index,_writes,_stats}` (per-type in-memory indexes, snapshot swap, pytricia-or-`ipaddress` CIDR fallback, `get_metrics()`); shared `storage_base` (schema, `resolve_db_path` env→platformdirs chain, `normalize_url`, `StorageProtocol`).
- **Check semantics** — domain→URL cascade rules from `SecMCP.check` docstring; input typing (is_ip/is_url/is_domain heuristics).
- **MCP layer** — 6 tools, pydantic output models → `outputSchema`/`structuredContent`, `isError` boundary, `notifications/progress` bridging via `anyio.from_thread`.
- **Config & data locations** — `config.json` keys; `MCP_DB_PATH`/`MCP_LOG_PATH`/`MCP_CACHE_DIR`/`MCP_DISABLE_SCHEDULER`; platformdirs defaults per OS.
- **Cross-links** — `docs/decisions/` ADRs (pytricia opt-in, coverage M3 target), `docs/agent-env.md` for probe-isolation rationale, `BENCHMARK_PLAYBOOK.md`.

### `docs/DEVELOPMENT.md`
- Deliberately thin — links, not copies: dev setup/test/lint/coverage → `CONTRIBUTING.md`; env vars + probe isolation → `docs/agent-env.md`; conventions summary (branch `<type>/<issue>-<slug>`, Conventional Commits w/ issue ref, squash-merge).
- Repo layout recap (package vs `react-landing-page/` vs `scripts/` vs `docs/`); where tests live (`sec_mcp/tests/`, `pytest.ini` testpaths, hermetic `conftest.py`, `scripts/check_test_baseline.sh` floor).
- CI gates recap: `ci.yml` (build → ruff → baseline → `--cov-fail-under=98` on py3.11–3.14; landing-page `npm ci && npm run build` on PRs), pre-commit hooks mirror CI.
- Pointers: ADR process (`docs/decisions/`), historical PRD in `docs/archive/`.

### `docs/DEPLOYMENT.md`
- **PyPI release** — tag-driven: bump `pyproject.toml` version → merge → push `vX.Y.Z`; `pypi-publish.yml` verifies tag==version, builds, lints, baseline gate, publishes via `PYPI_API_TOKEN` (no trusted publisher); MCP Registry metadata in `server.json` (per-package version must be bumped too — note `test_server_json.py` guards it).
- **End-user deployment** — `pip install sec-mcp` / `uvx --from sec-mcp sec-mcp-server`; MCP client JSON config (README block); stdio transport only; env vars for production paths; `sec-mcp update` before first serve; scheduler + rate-limit behavior.
- **Landing page** — `deploy-landing-page.yml`: push to main touching `react-landing-page/**` → Node 24 `npm ci`/`npm run build` → `actions/deploy-pages` to `https://montimage.github.io/sec-mcp/`.
- **Operational notes** — feed HTTPS bounds (`max_feed_bytes`, `min/max_feed_entries`, `max_range_addresses`), log/cache locations, `MCP_DISABLE_SCHEDULER=1` for embedded use.

---

## Manual steps & open questions

**Q1 — Contact addresses (blocks CoC + SECURITY + templates):** confirm the contact email.
Task brief suggests `luong.nguyen@montimage.eu`; README lists `contact@montimage.eu`.
Pick one for: CoC `[INSERT CONTACT METHOD]`, SECURITY.md primary channel, and optionally
the issue-template `config.yml` contact link.

**Q2 — Security reporting channel (audit bonus item):** two-part fix, both recommended:
(a) **manual GitHub step** — enable private vulnerability reporting (repo Settings →
Security → "Private vulnerability reporting"); then SECURITY.md's existing advisories URL
works as written. (b) SECURITY.md edit regardless — email as the always-available channel,
advisories URL kept as preferred once enabled.

**Q3 — License scope:** confirm Apache-2.0 applies to `react-landing-page/` too
(`package.json`, its README, `public/index.md` copy) — assumed yes, same repo.

**Q4 — Apache copyright line:** holder name/year for the LICENSE appendix/NOTICE-style
attribution — `Copyright 2025 Luong NGUYEN` (current MIT line) vs `Montimage`.

**Q5 — pyproject license format:** `license = "Apache-2.0"` is PEP 639 SPDX syntax —
requires setuptools ≥77 at build time (build-system currently pins `>=61`). It already
uses string form for MIT without issue in CI, so swapping the string is equivalent-risk;
optionally bump `requires = ["setuptools>=77", ...]` for strict PEP 639 correctness.

**Branch/PR note:** per repo convention this lands on a `docs/` or `chore/` branch with an
issue ref — e.g. `docs/<issue>-oss-community-docs`; commit `docs(oss): ... (#<issue>)`.
License change + community files + docs can be one PR or split (license/meta vs docs) —
recommend one PR since README/CHANGELOG tie them together.
