# Deployment

Three deploy surfaces: the PyPI package, the end-user MCP server, and the
GitHub Pages landing site.

## PyPI release (maintainers)

Releases are tag-driven:

1. Bump `version` in `pyproject.toml` — and `version` / `packages[].version`
   in `server.json` (MCP Registry metadata; `sec_mcp/tests/test_server_json.py`
   guards the match).
2. Merge to `main`, then push a `v<version>` tag.

`.github/workflows/pypi-publish.yml` triggers on `v*.*.*` tags and runs:

- verify tag == `pyproject.toml` version,
- `uv sync --frozen`, `python -m build`, `ruff check`,
  `scripts/check_test_baseline.sh`,
- upload `dist/` to PyPI via `pypa/gh-action-pypi-publish` using the
  `PYPI_API_TOKEN` secret — token auth, no trusted publisher is registered
  for this repo's OIDC claims (see the comment in the workflow).

## End-user deployment (MCP server / CLI)

The published package provides two console scripts
(`pyproject.toml` `[project.scripts]`):

- `sec-mcp` — CLI (`sec_mcp.cli:cli`)
- `sec-mcp-server` — MCP server over **stdio only** (`sec_mcp.start_server:main`)

Install and first-run:

```bash
pip install sec-mcp        # or: uvx --from sec-mcp sec-mcp update
sec-mcp update             # download + index the feeds — required once
```

MCP client configuration (Claude Desktop, Cursor, Windsurf, …):

```json
{
  "mcpServers": {
    "sec-mcp": {
      "command": "uvx",
      "args": ["--from", "sec-mcp", "sec-mcp-server"],
      "env": { "MCP_USE_V2_STORAGE": "true" }
    }
  }
}
```

`server.json` at the repo root ships the matching MCP Registry entry
(`io.github.montimage/sec-mcp`, registry type `pypi`, `runtimeHint: uvx`,
stdio transport).

Production-relevant environment variables (full reference:
[agent-env.md](agent-env.md)):

| Variable | Use |
|----------|-----|
| `MCP_DB_PATH` | Pin the SQLite location (default: platformdirs user data dir) |
| `MCP_USE_V2_STORAGE` | `true` selects the in-memory `HybridStorage` backend |
| `MCP_LOG_PATH` | Log file location (default: platformdirs log dir) |
| `MCP_CACHE_DIR` | Feed download cache (default: platformdirs cache dir) |
| `MCP_DISABLE_SCHEDULER` | `1` disables the daily-update thread for embedded/one-shot use |

## Landing page (GitHub Pages)

`react-landing-page/` is a standalone Vite/React site.
`.github/workflows/deploy-landing-page.yml` deploys it:

- **Trigger:** push to `main`/`master` touching `react-landing-page/**`, or
  `workflow_dispatch`.
- **Build:** Node 24, `npm ci`, `npm run build` (Vite build + SSR prerender).
- **Deploy:** `actions/configure-pages` → `upload-pages-artifact` →
  `actions/deploy-pages` to <https://montimage.github.io/sec-mcp/>; one
  concurrent deployment (`concurrency: pages`).

### Agent discovery (DNS-AID)

The agent-readiness scanner (<https://isitagentready.com>) checks DNS for AI
Discovery (DNS-AID): ServiceMode `SVCB`/`HTTPS` records under
`_agents.montimage.github.io` in a DNSSEC-signed zone. That check cannot pass
on this host — `github.io` is GitHub's own zone and delegates no DNS control
to Pages sites, and no custom domain is configured
(`react-landing-page/public/CNAME` does not exist). DNS records cannot be
expressed as site files, so there is no in-repo fallback; the check stays
`fail` until a custom domain is adopted (tracked as issue #140).

When a custom domain is configured (`public/CNAME` plus registrar DNS),
publish leaf records under `_agents.<domain>` in a DNSSEC-signed zone — e.g.
`_index._agents.<domain>.` for the discovery index, or
`_a2a._agents.<domain>. 3600 IN SVCB 1 <endpoint>. alpn="a2a" port=443
mandatory=alpn,port` for an A2A endpoint — using numeric `keyNNNNN`
SvcParamKeys for experimental parameters. Guide:
<https://isitagentready.com/.well-known/agent-skills/dns-aid/SKILL.md>.
`sec_mcp/tests/test_landing_dns_aid.py` pins this note.

### Well-known agent manifests

`public/.well-known/` publishes the static agent-discovery manifests (issues
#143–#146, #148), all covered by `sec_mcp/tests/test_landing_agent_manifests.py`:

| Deployed path | Manifest |
|---------------|----------|
| `/sec-mcp/.well-known/agent-card.json` | A2A Agent Card — interfaces, capabilities, skills |
| `/sec-mcp/.well-known/agent-skills/index.json` | agentskills.io discovery index (sha256 digests) |
| `/sec-mcp/.well-known/agent-skills/sec-mcp/SKILL.md` | the skill artifact the index references |
| `/sec-mcp/.well-known/api-catalog` | RFC 9727 linkset (created in #136, extended here) |
| `/sec-mcp/.well-known/ai-catalog.json` | ARD manifest cataloguing the siblings above |
| `/sec-mcp/.well-known/mcp/server-card.json` | MCP Server Card (SEP-2127), mirrors `server.json` |
| `/sec-mcp/.well-known/oauth-protected-resource` | RFC 9728 Protected Resource Metadata — `authorization_servers` is empty (#150) |

Two platform limitations keep the scanner's live-site acceptance checks red
regardless of this content:

- **Base path.** The site deploys under `/sec-mcp/`, so the manifests land at
  `/sec-mcp/.well-known/…`, while the scanner probes the origin root
  (`montimage.github.io/.well-known/…`). Nothing in-repo can serve the origin
  root — that needs a custom domain, same as DNS-AID above.
- **Content types.** GitHub Pages serves the extensionless `api-catalog` as
  `application/octet-stream`, not `application/linkset+json`, and emits no
  `Access-Control-Allow-Origin` header — Pages does not let a static site set
  response headers.

The documents are still correct and interlinked (`<link rel="ai-catalog">` in
`index.html`, `Agentmap:` in `robots.txt`, catalog cross-references), so the
surface resolves as soon as a custom domain with header control is adopted.

### Agent authentication (auth.md and OAuth metadata)

Issues #147–#150 ask for the agent-auth discovery surface the
[isitagentready.com](https://isitagentready.com) guides describe. sec-mcp has
**no authorization server and no protected HTTP API** — the site is static
and public, and the MCP server is a local stdio process — so the shipped
deliverables are the truthful subset:

- `public/auth.md` → `/sec-mcp/auth.md`: a self-contained Auth.md statement
  following the guide's no-OAuth path — it identifies the agent audience,
  states there is no registration/provisioning endpoint, lists `none` as the
  supported method and explains that no credentials are used (#147).
- `public/.well-known/oauth-protected-resource` → RFC 9728 Protected
  Resource Metadata naming `https://montimage.github.io/sec-mcp/` as the
  `resource` with an **empty** `authorization_servers` array — the accurate
  answer to "how do agents authenticate" is "they don't; no authorization
  server exists" (#150).
- **Deliberately absent:** `/.well-known/oauth-authorization-server` and
  `/.well-known/openid-configuration` (#149). RFC 8414 / OIDC Discovery
  metadata describes a live issuer and its endpoints; sec-mcp runs no issuer,
  so any document at those paths would fabricate `authorization_endpoint`,
  `token_endpoint` or `jwks_uri` values. A `404` is the honest signal that no
  authorization server serves this origin. If a protected HTTP API is ever
  added, publish the AS metadata then — this note is the runbook.

The GitHub Pages limitations of the other manifests apply here too: the
scanner probes `montimage.github.io/auth.md` and
`montimage.github.io/.well-known/…` at the **origin root** while the files
deploy under `/sec-mcp/`, and the extensionless PRM document is served as
`application/octet-stream`. So `authMd` and `oauthProtectedResource` stay
`fail` until a custom domain lands, and `oauthDiscovery` additionally
requires a real authorization server this service does not run.
`sec_mcp/tests/test_landing_auth_metadata.py` pins this surface.

## Operational notes

- Feeds are downloaded over **HTTPS only** (non-HTTPS sources are rejected),
  bounded by `max_feed_bytes`, and sanity-checked against
  `min_feed_entries`/`max_feed_entries` — a failing feed keeps existing data.
  `max_range_addresses` caps expanded CIDR ranges. All bounds live in
  `sec_mcp/config.json`.
- `update_blacklists`/`sec-mcp update` is rate limited to one forced update
  per `min_update_interval_seconds` (default 300); the scheduled daily update
  runs at `update_time`.
- One source's failure is logged and skipped — it never aborts the remaining
  feeds.
- Log/cache/database locations default to platformdirs paths and are
  overridable per environment (table above).
