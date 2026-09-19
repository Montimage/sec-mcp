# Step 2 — Branch Inventory & Classification

**Repo:** Montimage/sec-mcp · **Default branch:** main · **Scan date:** 2026-09-19
**Method:** `git fetch --all --prune`, `git rev-list --left-right --count main...<branch>`,
`git branch [-r] --merged main`, `gh pr list --state all`.

> **Note on "ahead" counts:** this repo squash-merges PRs, so a merged PR's branch
> still shows 1–2 commits "ahead" of main (the pre-squash commits are not ancestors
> of main). For remote branches, the **PR merged state is authoritative**, not raw
> git ancestry.

## Summary

| Scope | Count |
|---|---|
| Local branches | 3 |
| Remote branches (origin, excl. HEAD symref) | 16 |
| Open PRs | 0 |

| Category | Count |
|---|---|
| protected-do-not-touch | 1 (main, local + remote) |
| merged-safe-to-delete | 15 (1 local-only + 14 remote-only) |
| unmerged-needs-review | 1 (local + remote pair) |
| stale-no-activity-90d | 0 (the unmerged branch is also >90d stale — dual-flagged) |
| active-recent | 0 |

During the scan, `git fetch --prune` dropped 5 stale remote-tracking refs whose
branches were already deleted on GitHub (refactor/58-*, refactor/61-*,
refactor/7-*, test/8-*, test/9-* — all merged via PRs #64, #66, #67, #119, #131).
No remote branches were deleted by this scan; this was local ref cleanup only.

---

## protected-do-not-touch

| Branch | Scope | Ahead/Behind vs main | Last commit | Proposed action |
|---|---|---|---|---|
| `main` | local + `origin/main` | 0 / 0 | 2026-09-19, Luong NGUYEN — `chore(release): v0.5.0` | **Keep** — default branch. `origin/HEAD` symref points here. |

No `release/*` or `gh-pages` branches exist.

## merged-safe-to-delete

PR state confirms every one of these was merged (squash-merge). The residual
"ahead" commits are the pre-squash originals; their content is in main.

| Branch | Scope | Ahead/Behind | Last commit (all: Luong NGUYEN) | Merged PR | Proposed action |
|---|---|---|---|---|---|
| `claude/review-sec-mcp-server-016n1PyTorrbKMAHJHRWU7dV` | local only (upstream gone) | 0 / 63 | 2025-11-23 — `feat: Optimize MCP tools and reorganize project documentation` | #2 (MERGED 2025-11-22) | **Delete local** — true ancestor of main |
| `feat/35-3-7-tool-annotations` | remote | 1 / 23 | 2026-09-19 — `feat(mcp): add tool annotations (#35)` | #113 MERGED | **Delete remote** |
| `feat/36-3-8-structured-output-and-error-semantics` | remote | 1 / 22 | 2026-09-19 — `feat(mcp): structured output + isError (#36)` | #114 MERGED | **Delete remote** |
| `feat/37-3-9-server-identity-and-input-schemas` | remote | 1 / 21 | 2026-09-19 — `feat(mcp): server identity, input schemas (#37)` | #115 MERGED | **Delete remote** |
| `feat/39-4-1-mcp-registry-metadata-and-client` | remote | 1 / 20 | 2026-09-19 — `feat(mcp): Registry server.json, uvx config (#39)` | #116 MERGED | **Delete remote** |
| `fix/28-pypi-publish-token-auth` | remote | 1 / 28 | 2026-09-19 — `fix(ci): publish via PYPI_API_TOKEN (#28)` | #108 MERGED | **Delete remote** |
| `fix/38-3-10-rate-limiting-progress-honest-health` | remote | 1 / 19 | 2026-09-19 — `fix(mcp): rate-limit, progress, honest health (#38)` | #117 MERGED | **Delete remote** |
| `refactor/28-2-7-publish-a-fixed-release-to-pypi` | remote | 1 / 29 | 2026-09-19 — `chore(release): 0.4.0 release notes (#28)` | #107 MERGED | **Delete remote** |
| `refactor/34-3-6-major-mcp-sdk-1-x-2-x-and` | remote | 1 / 26 | 2026-09-19 — `refactor(mcp): SDK 1.x→2.x (#34)` | #110 MERGED | **Delete remote** |
| `refactor/41-4-3-major-vitejs-plugin-react-4-6` | remote | 1 / 32 | 2026-09-19 — `chore(deps-dev): @vitejs/plugin-react 5→6 (#41)` | #104 MERGED | **Delete remote** |
| `refactor/42-4-4-major-react-syntax-highlighter` | remote | 1 / 31 | 2026-09-19 — `chore(deps): react-syntax-highlighter 15→16 (#42)` | #105 MERGED | **Delete remote** |
| `refactor/43-4-5-major-react-react-dom-18-19` | remote | 1 / 30 | 2026-09-19 — `chore(deps): react + react-dom 18→19 (#43)` | #106 MERGED | **Delete remote** |
| `refactor/44-4-6-major-tailwindcss-3-4` | remote | 2 / 27 | 2026-09-19 — `docs(landing-page): Tailwind v4 review feedback (#44)` | #109 MERGED | **Delete remote** |
| `refactor/59-6-4-landing-page-content-matches-the` | remote | 1 / 25 | 2026-09-19 — `fix(landing-page): sync content with MCP server (#59)` | #111 MERGED | **Delete remote** |
| `refactor/60-6-5-landing-page-navigation-and` | remote | 1 / 24 | 2026-09-19 — `fix(landing-page): nav order/affordances (#60)` | #112 MERGED | **Delete remote** |

## unmerged-needs-review

| Branch | Scope | Ahead/Behind | Last commit | PR | Proposed action |
|---|---|---|---|---|---|
| `claude/improve-project-quality-01H2ugpChCcQPKYU77oGAdgQ` | local + remote | **12 ahead** / 62 behind | 2025-11-23, Luong NGUYEN — `docs: Update documentation to reflect 3-tool MCP server API` | none ever opened | **User review required** — do not delete yet |

Dual-flagged: also **stale** — last activity ~301 days ago (>90d threshold).

Unmerged commits (12), oldest → newest:

| # | SHA | Date | Title |
|---|---|---|---|
| 1 | ad2461a | 2025-11-22 | feat: Set up comprehensive pre-commit hooks and code quality tools |
| 2 | 4f212b8 | 2025-11-23 | feat: Add HTTP transport support and improved server startup UX |
| 3 | bc21df8 | 2025-11-23 | test: Add comprehensive tests for MCP server and startup (Phase 2 partial) |
| 4 | 5444dce | 2025-11-23 | chore: Remove accidentally created :memory: file |
| 5 | 5e73021 | 2025-11-23 | test: Add comprehensive unit tests to increase coverage to 69% |
| 6 | 756b7d0 | 2025-11-23 | test: Add update_blacklist tests, coverage now at 71.54% |
| 7 | 4f6fdf3 | 2025-11-23 | chore: Remove accidentally created :memory: file |
| 8 | cd46f15 | 2025-11-23 | fix: Add sec-mcp-server entry point to setup.py |
| 9 | 91f8569 | 2025-11-23 | feat: Enable v2 storage by default and fix HTTP server configuration |
| 10 | 4d77655 | 2025-11-23 | feat: Enhanced server startup messages with copy-paste ready configurations |
| 11 | b5f569f | 2025-11-23 | refactor: Streamline MCP tools to 3 essential functions |
| 12 | f9b73a6 | 2025-11-23 | docs: Update documentation to reflect 3-tool MCP server API |

`git diff main...` stat: 47 files, +2964/−1032 — a large, divergent body of work.
Much of its intent (3-tool MCP API, pre-commit hooks, higher coverage, HTTP server
UX) appears **superseded** by the Sept-2026 modernization series already in main
(PR #1 merged some of this line of work; issues #4–#61 re-did it properly).
Verifying whether anything unique remains requires manual diff review.

## stale-no-activity-90d

None beyond the dual-flagged `claude/improve-project-quality-*` above.

## active-recent

None. All branches with 2026-09-19 activity are already merged.

---

## Proposed action checklist (for user approval — nothing executed)

1. `git branch -d claude/review-sec-mcp-server-016n1PyTorrbKMAHJHRWU7dV` (safe `-d`, it is an ancestor of main).
2. `git push origin --delete` for the 14 merged remote branches listed above (or use GitHub's "delete branch" on the merged PR pages).
3. **Decide** on `claude/improve-project-quality-01H2ugpChCcQPKYU77oGAdgQ`:
   - salvage: open a PR or cherry-pick any unique work, or
   - discard: `git branch -D` + `git push origin --delete`.
4. `main` — no action.

---

## Action Log (executed 2026-09-19)

All actions below were individually approved by the user via per-branch prompts.

| Branch | Action | Result |
|---|---|---|
| feat/35-3-7-tool-annotations | remote delete | done |
| feat/36-3-8-structured-output-and-error-semantics | remote delete | done |
| feat/37-3-9-server-identity-and-input-schemas | remote delete | done |
| feat/39-4-1-mcp-registry-metadata-and-client | remote delete | done |
| fix/28-pypi-publish-token-auth | remote delete | done |
| fix/38-3-10-rate-limiting-progress-honest-health | remote delete | done |
| refactor/28-2-7-publish-a-fixed-release-to-pypi | remote delete | done |
| refactor/34-3-6-major-mcp-sdk-1-x-2-x-and | remote delete | done |
| refactor/41-4-3-major-vitejs-plugin-react-4-6 | remote delete | done |
| refactor/42-4-4-major-react-syntax-highlighter | remote delete | done |
| refactor/43-4-5-major-react-react-dom-18-19 | remote delete | done |
| refactor/44-4-6-major-tailwindcss-3-4 | remote delete | done |
| refactor/59-6-4-landing-page-content-matches-the | remote delete | done |
| refactor/60-6-5-landing-page-navigation-and | remote delete | done |
| claude/review-sec-mcp-server-016n1PyTorrbKMAHJHRWU7dV | local delete (`-d`, merged) | done |
| claude/improve-project-quality-01H2ugpChCcQPKYU77oGAdgQ | local delete (`-D`, 12 unmerged commits) + remote delete | done — user approved explicit loss of unmerged work |

**Final state:** `git branch -a` shows only `main` (+ `origin/HEAD` symref). Acceptance criterion met.

Note: the branch analyst's report used shortened names; actual remote refs carried full slugs — corrected at execution time. GitHub also reported 2 open Dependabot vulnerabilities on the default branch (1 critical, 1 moderate) — follow up at https://github.com/Montimage/sec-mcp/security/dependabot.
