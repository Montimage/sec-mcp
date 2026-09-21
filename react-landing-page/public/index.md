# sec-mcp — Know what you're talking to

> Check domains, URLs and IP addresses against ten live blacklist feeds — in process, in microseconds, with no API key and no request leaving your machine. Python 3.11+ · Apache-2.0 license · use it as a library, a CLI, or an MCP server.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install sec-mcp
sec-mcp update          # downloads and indexes the feeds — required once
sec-mcp check example.com
```

## Features

- **Ten feeds, one index** — each source is parsed per format, normalised, and stored in one local SQLite index.
- **Microsecond lookups** — a domain check is a memory read (~0.006 ms); the full index of ~450K entries is about 45 MB.
- **Three ways in** — Python library, terminal CLI, or MCP server for LLM clients.
- **CIDR-aware IP matching** — an address is flagged if any containing network is blacklisted.
- **Refreshed on a schedule** — feeds update themselves on a background timer.
- **Safe under concurrency** — the index is read-only after build, so threads and processes share it freely.

## Blacklist feeds (10)

| Feed | Covers | Kind |
|---|---|---|
| OpenPhish | Live phishing URLs | URL |
| PhishStats | Scored phishing URLs | URL |
| URLhaus | Malware distribution URLs | URL |
| PhishTank | Community-verified phishing | URL |
| Spamhaus DROP | Hijacked and rogue netblocks | CIDR |
| DShield | Most-attacking networks | CIDR |
| CINS Score | Poorly-reputed addresses | IP |
| Emerging Threats | Compromised hosts | IP |
| Feodo Tracker | Botnet command & control | IP |
| Blocklist.de | Reported attacking hosts | IP |

## Python API

Nine methods and two dataclasses — the whole surface:

- `check(value) -> CheckResult` — infers domain, URL or IP
- `check_domain(domain)`, `check_url(url)`, `check_ip(ip)` -> `CheckResult`
- `check_batch(values) -> List[CheckResult]` — results in input order
- `get_status() -> StatusInfo` — entry count, last update, active sources
- `update() -> dict` — force a feed refresh (rate limited)
- `sample(count=10) -> List[str]` — random indexed entries
- `scheduler_alive() -> bool` — background update thread health

Every check returns a `CheckResult`: a boolean `is_safe` and a sentence explaining it. `StatusInfo` describes the index.

## MCP server

Run `sec-mcp` as an MCP server and six tools appear in your client, so the model can verify a link mid-conversation instead of guessing at it:

- `check_batch(values)` — check multiple domains/URLs/IPs in one call
- `get_status()` — entry counts, sources, server status
- `update_blacklists()` — force immediate refresh
- `get_diagnostics(mode)` — `summary`, `full`, `health`, `performance`, `sample`
- `add_entry(url, ip, date, score, source)` — manual blacklist entry
- `remove_entry(value)` — remove an entry by URL or IP

## Try it in the browser

The landing page has a live console for the MCP server. It answers from a labelled demo dataset until you connect your own server:

```bash
pip install sec-mcp && sec-mcp update
sec-mcp-server --http        # serves http://127.0.0.1:8000/mcp
```

Then press **Connect** in the console. `SEC_MCP_CORS_ORIGINS` allows extra web origins; `SEC_MCP_HTTP_AUTH_TOKEN` requires a bearer token.

## Links

- Repository: https://github.com/montimage/sec-mcp
- Package: https://pypi.org/project/sec-mcp/
- MCP documentation: https://modelcontextprotocol.io/examples
- Publisher: https://www.montimage.eu
