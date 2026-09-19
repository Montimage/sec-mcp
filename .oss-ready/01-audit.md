# OSS-Ready Audit — Step 1 Report

- **Repo:** `/Users/montimage/workspace/montimage/sec-mcp` (`Montimage/sec-mcp`, PUBLIC)
- **Skill:** `oss-ready` v1.3.0 (`/Users/montimage/.agents/skills/oss-ready/SKILL.md`)
- **Audited:** `main` @ `9aaea5f` ("chore(release): v0.5.0"), up to date with `origin/main`
- **GitHub community health:** 75% (`gh api repos/Montimage/sec-mcp/community/profile`)

## Overall verdict: **PARTIAL**

Core files (LICENSE, README, CONTRIBUTING, SECURITY), metadata, .gitignore and
GitHub-side basics are all in place. Missing: CODE_OF_CONDUCT.md, all GitHub
issue/PR templates, and the `docs/` structure files (ARCHITECTURE / DEVELOPMENT /
DEPLOYMENT). One integrity issue: SECURITY.md routes reports through GitHub
private vulnerability reporting, which is currently **disabled** on the repo.

---

## (a) Per-section pass/fail counts

| Section | Scope | Done / Applicable | Missing | n/a |
|---|---|---|---|---|
| S1 | Core community files | 3/4 | 1 | 0 |
| S2 | README content | 8/8 | 0 | 0 |
| S3 | GitHub issue/PR templates | 0/3 | 3 | 0 |
| S4 | Documentation structure | 1/4 | 3 | 0 |
| S5 | Project metadata (pyproject.toml) | 3/3 | 0 | 0 |
| S6 | .gitignore | 1/1 | 0 | 0 |
| S7 | Repo/git state (non-destructive) | 3/3 | 0 | 0 |
| S8 | GitHub-side community health | 5/6 | 0 | 1 |
| Bonus | Extras beyond the checklist | 5/6 | 1 | 0 |
| **Total** | | **32/39** | **7** | **1** |

---

## Checklist detail

### S1 — Core community files (3/4)

| Item | Status | Evidence |
|---|---|---|
| `LICENSE` exists with valid SPDX identifier | done | `LICENSE:1` "MIT License"; GitHub detects `mit` (`licenseInfo.key`); `pyproject.toml` `license = "MIT"` |
| `CONTRIBUTING.md` references issue tracker + branch/PR workflow | done | `CONTRIBUTING.md` — 15 hits for `issue\|pull request\|branch`; branching `<type>/<issue>-<slug>` (L83), Conventional Commits (L86), full PR process (L95-104), issues link (L117) |
| `CODE_OF_CONDUCT.md` exists, mentions Contributor Covenant | **missing** | No such file at root or anywhere in repo (`ls`/`find`); `gh api …/community/profile` → `code_of_conduct: null` |
| `SECURITY.md` exists with reporting contact/URL | done | `SECURITY.md` — reporting via `https://github.com/Montimage/sec-mcp/security/advisories/new` + Montimage org profile fallback. ⚠ See Bonus item: that reporting feature is currently disabled on the repo |

### S2 — README content (8/8)

| Item | Status | Evidence |
|---|---|---|
| Exists, ≥40 lines | done | `README.md` — 532 lines |
| Installation section | done | `README.md:48` `## Installation` (+ Requirements L54) |
| Usage section | done | `README.md:92` `## Usage` (CLI, Python API, MCP Server subsections) |
| License section | done | `README.md:504` `## License` → links `LICENSE` |
| Overview + motivation | done | L1-16 header + PyPI/pyversions/license badges |
| Features list | done | L35 `## Features` |
| Quick start (<5 min) | done | L62 `## Quick Start` |
| Project structure + contributing link + license badge | done | Structure L471; Contributing L522 → `CONTRIBUTING.md`; MIT badge L13 |

### S3 — GitHub templates (0/3)

| Item | Status | Evidence |
|---|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.md` (YAML frontmatter) | **missing** | `.github/` contains only `dependabot.yml` + `workflows/`; `issue_template: null` in community profile |
| `.github/ISSUE_TEMPLATE/feature_request.md` (YAML frontmatter) | **missing** | Same as above |
| `.github/PULL_REQUEST_TEMPLATE.md` with `- [ ]` checklist | **missing** | Not on disk; `pull_request_template: null` in community profile |

### S4 — Documentation structure (1/4)

| Item | Status | Evidence |
|---|---|---|
| `docs/ARCHITECTURE.md` | **missing** | `docs/` has `agent-env.md`, `playbook.md`, `decisions/`, `archive/` — no ARCHITECTURE.md |
| `docs/DEVELOPMENT.md` | **missing** | Dev-setup content exists but is split across `CONTRIBUTING.md` and `docs/agent-env.md`; no DEVELOPMENT.md file |
| `docs/DEPLOYMENT.md` | **missing** | No deployment doc (PyPI release notes exist in CONTRIBUTING.md "Releasing" section) |
| `docs/CHANGELOG.md` | done (alt. location) | `CHANGELOG.md` at **repo root** — Keep a Changelog format, versions through `[0.5.0]`, linked from README L524 and CONTRIBUTING L104. Substance met; not under `docs/` |

### S5 — Project metadata (3/3)

| Item | Status | Evidence |
|---|---|---|
| `license` declared | done | `pyproject.toml` `license = "MIT"` |
| `description` declared | done | `description = "Python toolkit providing security checks for domains, URLs, IPs, and more."` |
| `repository` declared | done | `[project.urls] Repository = "https://github.com/Montimage/sec-mcp.git"` (plus Homepage, Documentation; keywords present) |

### S6 — .gitignore (1/1)

| Item | Status | Evidence |
|---|---|---|
| Language-appropriate build/temp artifacts excluded | done | `.gitignore` — `__pycache__/`, `dist/`, `*.egg-info/`, `.venv`, `.coverage`, `.pytest_cache/`, `*.db`/WAL sidecars, `node_modules/`, Vite paths, `.env`, secrets (`*.pem`, `*.key`) |

### S7 — Repo/git state (3/3)

| Item | Status | Evidence |
|---|---|---|
| On a stable branch, synced with remote | done | `main`, "up to date with 'origin/main'" |
| No deleted/modified tracked files | done | `git status` — only untracked paths (`.gitissue*`, `CODE_REVIEW.md`, `MODERNIZATION_*`, `react-landing-page/.agent-ready*`) |
| Repo is public (audit target confirmed) | done | `gh repo view` → `visibility: PUBLIC`, `isPrivate: false` |

### S8 — GitHub-side community health (5/6, 1 n/a)

| Item | Status | Evidence |
|---|---|---|
| Repo description set | done | "A Python toolkit providing security checks for domains, URLs, IPs, and more. …" |
| License detected by GitHub | done | `licenseInfo.key = mit` |
| Topics set | done | `mcp-server`, `security-tools` (sparse — could add `python`, `mcp`, `threat-intelligence`, `cli`) |
| Issues enabled | done | `hasIssuesEnabled: true` |
| Homepage URL set | done | `https://montimage.github.io/sec-mcp/` (landing page deployed via `deploy-landing-page.yml`) |
| Discussions enabled | n/a | `hasDiscussionsEnabled: false` — optional, not required by the checklist |

### Bonus (5/6)

| Item | Status | Evidence |
|---|---|---|
| CI workflow | done | `.github/workflows/ci.yml` (multi-Python 3.11-3.14, ruff, coverage gate `--cov-fail-under=98`) |
| Release/publish workflow | done | `.github/workflows/pypi-publish.yml` (tag-driven PyPI publish) |
| Dependency automation | done | `.github/dependabot.yml` (uv weekly + grouped minor/patch; npm + github-actions entries below line 25) |
| Contributor tooling (pre-commit, AGENTS.md, registry metadata) | done | `.pre-commit-config.yaml`, `AGENTS.md`, `CLAUDE.md`, `server.json` (MCP Registry) |
| Dev docs extras | done | `docs/agent-env.md`, `docs/playbook.md`, `docs/decisions/` (ADRs), `BENCHMARK_PLAYBOOK.md` |
| GitHub private vulnerability reporting enabled | **missing** | `gh api repos/Montimage/sec-mcp/private-vulnerability-reporting` → `{"enabled": false}` — yet SECURITY.md tells reporters to use "Security tab → Advisories → Report a vulnerability". Either enable the feature or change SECURITY.md's reporting path |

---

## (b) Flat list of missing items

1. `CODE_OF_CONDUCT.md` (Contributor Covenant) — S1
2. `.github/ISSUE_TEMPLATE/bug_report.md` — S3
3. `.github/ISSUE_TEMPLATE/feature_request.md` — S3
4. `.github/PULL_REQUEST_TEMPLATE.md` — S3
5. `docs/ARCHITECTURE.md` — S4
6. `docs/DEVELOPMENT.md` — S4 (content partially covered by CONTRIBUTING.md + docs/agent-env.md)
7. `docs/DEPLOYMENT.md` — S4
8. GitHub private vulnerability reporting disabled while SECURITY.md routes reports to it — Bonus (manual GitHub setting, or SECURITY.md edit)

## (c) Flat list of items already done

1. `LICENSE` — MIT, detected by GitHub, matches pyproject (S1)
2. `CONTRIBUTING.md` — dev setup, branching, Conventional Commits, PR process, testing/coverage gates (S1)
3. `SECURITY.md` — supported-versions table + private reporting path + fallback contact (S1)
4. `README.md` — 532 lines; Installation, Usage, License, Features, Quick Start, Project Structure, badges, Contributing link (S2, all 8 sub-items)
5. `CHANGELOG.md` at root — Keep a Changelog, releases through 0.5.0 (S4, alternate location)
6. `pyproject.toml` — license, description, repository, homepage, keywords, classifiers (S5)
7. `.gitignore` — comprehensive Python + Node/Vite + secrets + DB-sidecar coverage (S6)
8. Clean synced `main`, public repo, no deleted tracked files (S7)
9. GitHub description, license detection, topics, issues, homepage (S8)
10. CI (`ci.yml`), PyPI publish (`pypi-publish.yml`), landing-page deploy workflow (Bonus)
11. `dependabot.yml` with uv/npm/actions ecosystems (Bonus)
12. `.pre-commit-config.yaml`, `AGENTS.md`, `CLAUDE.md`, `server.json` MCP registry metadata (Bonus)

## (d) Recommended priority order for remaining work

| # | Item | Why first |
|---|---|---|
| 1 | `CODE_OF_CONDUCT.md` | One-file fix, largest community-health boost (GitHub counts it); template ready in skill `assets/CODE_OF_CONDUCT.md` |
| 2 | `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.md` + `PULL_REQUEST_TEMPLATE.md` | Second-largest health gap; templates exist in skill `assets/.github/`; aligns with CONTRIBUTING's `Closes #<issue>` PR convention |
| 3 | Fix security reporting path | Enable private vulnerability reporting in repo settings (preferred — SECURITY.md already assumes it), or edit SECURITY.md to a working contact |
| 4 | `docs/ARCHITECTURE.md` | Real gap — storage v1/v2 split, MCP server, feed ingestion would benefit from a design doc |
| 5 | `docs/DEVELOPMENT.md` | Mostly a consolidation job — CONTRIBUTING.md + docs/agent-env.md already hold the content |
| 6 | `docs/DEPLOYMENT.md` | Lowest value — PyPI release flow is already documented in CONTRIBUTING.md "Releasing" |

## Notes for the next step (Fixer)

- Untracked files exist (`.gitissue*`, `CODE_REVIEW.md`, `MODERNIZATION_*.md`, `react-landing-page/.agent-ready*`) — do not delete or commit them; out of audit scope.
- `dev-docs/` is gitignored and `docs/archive/` holds historical PRD/tasks — do not count as the `docs/` structure files.
- Non-destructive rule: all work is additive — nothing needs to be overwritten.
