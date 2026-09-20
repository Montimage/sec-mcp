---
name: sec-mcp
description: Check domains, URLs and IP addresses against ten aggregated security blacklists (OpenPhish, PhishStats, URLhaus, PhishTank, Spamhaus DROP, DShield, CINS Score, Emerging Threats, Feodo Tracker, Blocklist.de) via the sec-mcp MCP server or Python library — in-process, no API key, no request leaving the machine.
license: Apache-2.0
metadata:
  homepage: https://montimage.github.io/sec-mcp/
  repository: https://github.com/Montimage/sec-mcp
  package: https://pypi.org/project/sec-mcp/
---

# sec-mcp — blacklist checks for indicators

Use this skill when you need to know whether a domain, URL or IP address is
malicious. sec-mcp keeps a local SQLite index of ten public threat-intelligence
feeds, so lookups are in-process and take microseconds.

## Setup

```bash
pip install sec-mcp        # or run anything below via: uvx --from sec-mcp <cmd>
sec-mcp update             # download and index the feeds — required once
```

## Use it as an MCP server

Register `uvx --from sec-mcp sec-mcp-server` (stdio) in your MCP client. Six
tools appear:

| Tool | What it does |
|------|--------------|
| `check_batch(values)` | Check multiple domains/URLs/IPs in one call; returns `{value, is_safe, verdict, explanation}` per indicator |
| `get_status()` | Entry counts, per-source breakdown, last update, `scheduler_alive` |
| `update_blacklists()` | Force a feed refresh (rate limited; emits per-source progress) |
| `get_diagnostics(mode)` | `summary` (default), `full`, `health`, `performance`, `sample` |
| `add_entry(url, ip, date, score, source)` | Add a manual blacklist entry |
| `remove_entry(value)` | Remove an entry by domain, URL or IP |

Every tool publishes a typed `outputSchema` and returns `structuredContent`;
domain failures surface as `isError` results.

## Use it from Python

```python
from sec_mcp import SecMCP

client = SecMCP()
result = client.check("example.com")   # CheckResult: is_safe + explanation
print(result.is_safe, result.explanation)
```

The same surface is available as a CLI: `sec-mcp check <value>`,
`sec-mcp update`, `sec-mcp status`.

## Notes

- A first `sec-mcp update` is mandatory — the index starts empty.
- IP checks are CIDR-aware: an address is flagged if any containing network is
  listed.
- `MCP_DB_PATH` overrides the SQLite location; `MCP_USE_V2_STORAGE=true`
  selects the in-memory backend.
