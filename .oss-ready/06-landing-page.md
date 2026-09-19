# Step 6 — Landing Page

## Status: SATISFIED (no new files needed)

GitHub Pages is already enabled and serving the project landing page:

- **URL:** https://montimage.github.io/sec-mcp/
- **Source:** `react-landing-page/` — standalone Vite/React site
- **Deploy:** `.github/workflows/deploy-landing-page.yml` (build_type: workflow, triggers on pushes to main touching `react-landing-page/**`, plus `workflow_dispatch`)
- **Pages config:** branch `main`, path `/`, HTTPS enforced

## Decision

User confirmed on 2026-09-19: mark satisfied, skip scaffolding. A separate Jekyll `docs/` site was deemed redundant and potentially conflicting with the existing workflow-based deployment.

## Notes

- The Docs Writer (step 3b) already updated landing-page license references (MIT → Apache-2.0) in `package.json`, `index.html`, `public/llms.txt`, `src/components/{Footer,Hero}.jsx`, `src/webmcp.js`. These changes will go live on the next Pages deployment.
- `react-landing-page/dist/` build artifacts still reference MIT — gitignored, refreshed automatically on next deploy.
