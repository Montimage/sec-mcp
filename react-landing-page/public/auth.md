# auth.md — sec-mcp agent authentication

**Audience:** agents and LLM clients that want to call sec-mcp's blacklist
checks — the `check_batch`, `get_status`, `update_blacklists`,
`get_diagnostics`, `add_entry` and `remove_entry` MCP tools.

## Authentication: none required

sec-mcp exposes **no remote HTTP API and no protected resources**. This
landing site is a static, fully public GitHub Pages site, and the MCP server
runs locally on the client's own machine over **stdio**
(`uvx --from sec-mcp sec-mcp-server`). No authorization server, token
endpoint, or credential of any kind exists or is needed — every blacklist
lookup executes in the caller's own process against a local SQLite index.

## Registration / provisioning

There is nothing to register and no provisioning endpoint: install the
package and start the server — no account, API key, or client credential is
created:

```bash
pip install sec-mcp        # or: uvx --from sec-mcp sec-mcp-server
sec-mcp update             # one-time feed download + index
```

MCP client configuration (Claude Desktop, Cursor, Windsurf, …):

```json
{
  "mcpServers": {
    "sec-mcp": {
      "command": "uvx",
      "args": ["--from", "sec-mcp", "sec-mcp-server"]
    }
  }
}
```

## Supported methods

- **none** — every interface (landing site, MCP tools, CLI, Python API) is
  usable without authentication.

## Credential use

No credentials are issued, accepted, or required. Agents must not send
`Authorization` headers or API keys — there is no endpoint that consumes
them.

## Discovery metadata

- OAuth Protected Resource Metadata (RFC 9728) is published at
  `/.well-known/oauth-protected-resource`; its `authorization_servers` list
  is empty because no authorization server exists for this service.
- No `/.well-known/oauth-authorization-server` or
  `/.well-known/openid-configuration` document is published: there is no
  issuer to describe, and publishing one would advertise endpoints that do
  not exist. A `404` from those paths is the correct signal.
