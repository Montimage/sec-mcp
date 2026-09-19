# Step 5 — Publications

## Baseline (repo scan)

**Result: EMPTY.** No publications, citations, or bibliographic material exist in
the repository. Specifically:

- **No** `CITATION.cff`, `*.bib`, `references.bib`, `AUTHORS`, or `NOTICE` files
  anywhere in the tree (tracked or untracked).
- **No DOIs, arXiv IDs, or BibTeX** strings in any tracked file. The only
  `doi.org` match is a literal example inside the step-5 TODO comment in the
  README (`README.md:401`).
- **No conference/journal names** (IEEE, ACM, USENIX, NDSS, CCS, S&P, etc.) in
  any tracked file. `PRAGMA journal_mode=WAL` in `sec_mcp/storage_base.py:22`
  is a SQLite directive, not a publication.
- **README** (`README.md:393-402`) contains a `## Related Publications` section
  that is an explicit placeholder for this step: "PLACEHOLDER — filled in by
  step 5 of the OSS-readiness flow… If no publications apply, delete the whole
  section." No actual entries.
- **README Acknowledgments** (`README.md:412-416`) lists threat-intel providers
  (OpenPhish, PhishStats, URLhaus, PhishTank, Spamhaus, Dshield, CINSSCORE,
  EmergingThreats, FeodoTracker, BlocklistDE) and the MCP Python SDK — no papers.
- **docs/** (`agent-env.md`, `ARCHITECTURE.md`, `DEPLOYMENT.md`,
  `DEVELOPMENT.md`, `playbook.md`, `decisions/`, `archive/prd.md`),
  `BENCHMARK_PLAYBOOK.md`, `dev-docs/*`, `MODERNIZATION_*.md`, `CODE_REVIEW.md`,
  `CHANGELOG.md`: no research references. `docs/playbook.md:53` "Research
  potential security incidents" is an incident-response instruction, not a
  citation.

### Search cues harvested for phase 2 (web search)

| Cue | Value | Source |
|---|---|---|
| Author (commits) | Luong NGUYEN <luongnv89@gmail.com> / <luongnv89@users.noreply.github.com> (sole human committer; other author is "Claude <noreply@anthropic.com>") | `git log` |
| Author (metadata) | "Montimage" (org-style author, no named individuals) | `pyproject.toml:12` |
| Org / website | Montimage — cybersecurity & network-monitoring company, https://www.montimage.eu, contact@montimage.eu | `README.md:17,388-389,408` |
| Project name variants | `sec-mcp`, `sec_mcp` (import), `sec-mcp-server` (script), `io.github.montimage/sec-mcp` (MCP Registry name) | `pyproject.toml:6,57-58`, `README.md:3` |
| Topic keywords | security, blacklist, mcp, phishing, malware | `pyproject.toml:32` |
| Domain context | threat intelligence, blacklist checking, MCP server for LLM agents; Montimage known for MMT (Montimage Monitoring Tool) — possible related papers under Montimage authors | `README.md`, general org context |

Suggested phase-2 queries: `"sec-mcp" Montimage`, `site:montimage.eu
publications`, `Luong Nguyen Montimage`, `Montimage MMT paper`, `Montimage
threat intelligence blacklist`, `site:hal.science Montimage`,
`site:dblp.org Montimage`.

## Phase 2 — User input (2026-09-19)

- User confirmed: no known publications citing or describing sec-mcp.
- External web search: declined by user.
- Result: final publications list is EMPTY (confirmed, valid per flow acceptance criteria).
- README `## Related Publications` section set to a minimal "none known yet" note with an invitation to open an issue.
