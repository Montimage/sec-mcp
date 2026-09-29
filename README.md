# sec-mcp

<!-- mcp-name: io.github.montimage/sec-mcp -->

**Check domains, URLs and IP addresses against live security blacklists — as a Python library, a terminal CLI, or an MCP server that gives LLM agents real-time threat context.**

<p align="left">
   <a href="https://github.com/Montimage/sec-mcp/actions/workflows/ci.yml"><img src="https://github.com/Montimage/sec-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
   <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/v/sec-mcp.svg?label=PyPI&color=blue" alt="PyPI"></a>
   <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/pyversions/sec-mcp.svg?label=Python&color=informational" alt="Python Versions"></a>
   <a href="https://pepy.tech/projects/sec-mcp"><img src="https://static.pepy.tech/badge/sec-mcp" alt="PyPI Downloads"></a>
   <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="Apache License 2.0"></a>
</p>

sec-mcp aggregates ten public threat-intelligence feeds into a local SQLite database and answers "is this domain/URL/IP malicious?" in microseconds. Use it inside any Python application, from the terminal with `sec-mcp`, or as a [Model Context Protocol](https://modelcontextprotocol.io/) server so tools like Claude Desktop, Cursor and Windsurf can screen indicators against real blacklist data.

Developed by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions.

---

## Table of Contents

- [Features](#features)
- [Demo](#demo)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
  - [CLI](#cli)
  - [Python API](#python-api)
  - [MCP Server](#mcp-server)
- [Performance Optimization](#performance-optimization)
- [Benchmarking](#benchmarking)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Related Publications](#related-publications)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Features

- **Comprehensive security checks** — validate domains, URLs and IPv4/IPv6 addresses, with domain→URL cascade semantics (a blacklisted domain condemns its URLs and subdomains; a blacklisted URL does not condemn its domain) and CIDR-range matching for IPs
- **Ten threat-intelligence feeds** — OpenPhish, PhishStats, URLhaus, PhishTank, Spamhaus DROP, Dshield, CINSSCORE, EmergingThreats, FeodoTracker and BlocklistDE
- **Three interfaces, one engine** — Python API (`SecMCP`), Click CLI (`sec-mcp`), and an MCP server (`sec-mcp-server`, stdio or streamable HTTP) exposing six typed tools
- **Two storage backends** — default SQLite storage (v1), or an in-memory hybrid (v2, `MCP_USE_V2_STORAGE=true`) with O(1) per-type indexes; up to ~28,000x faster lookups than the database-only path on the bundled benchmark
- **URL normalization** — one canonicalizer shared by both backends: lowercasing, default-scheme handling and tracking-parameter stripping (`utm_*`, `fbclid`, …), so URL variants share one verdict
- **Safe feed ingestion** — HTTPS-only downloads bounded by `max_feed_bytes` and entry-count sanity checks; a failing feed never aborts the others
- **Scheduled daily updates** — a `schedule` job refreshes feeds at `update_time`; forced updates are rate limited to one per `min_update_interval_seconds` (default 300 s)
- **Concurrency-friendly** — SQLite in WAL mode with `synchronous=NORMAL`, a thread-local shared connection per check, and lock-free snapshot reads on the v2 backend
- **Structured MCP output** — every tool publishes a typed `outputSchema`, results carry `structuredContent`, `check_batch` reports a tri-state verdict (`safe` / `blacklisted` / `invalid`), and domain failures surface as `isError` results instead of protocol crashes
- **Observable** — `get_diagnostics` MCP tool (summary / full / health / performance / sample modes), real `scheduler_alive` reporting and per-source entry counts

---

## Demo

> **PLACEHOLDER — needs maintainer input before publishing.** The repository ships no
> screenshot or demo assets today. Suggested: an asciinema recording of
> `sec-mcp update` → `sec-mcp check <url>`, or a screenshot of the six MCP tools
> inside Claude Desktop. Add the file under `docs/assets/` (e.g. `docs/assets/demo.gif`)
> and replace this block with `![sec-mcp demo](docs/assets/demo.gif)`.

---

## Quick Start

From zero to a verdict in under five minutes:

```bash
pip install sec-mcp
sec-mcp update                        # download + index the feeds (first run only)
sec-mcp check https://example.com     # → Status: Safe / Blacklisted
sec-mcp status                        # entry counts + per-source breakdown
```

To run it as an MCP server instead, jump to [MCP Server](#mcp-server) — no install beyond `uvx` is needed.

---

## Installation

```bash
pip install sec-mcp
```

### Requirements

- Python 3.11 or newer (CI tests 3.11–3.14)
- SQLite 3 (bundled with Python)
- Optional: `pytricia` via `pip install "sec-mcp[fast-cidr]"` for fast CIDR matching; without it a pure-Python `ipaddress` matcher is used (`pytricia` builds from source and needs a C compiler)

### From source

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv` if needed):

```bash
git clone https://github.com/Montimage/sec-mcp.git
cd sec-mcp
uv sync    # creates .venv, installs the package editable + dev tools, pinned by uv.lock
```

---

## Usage

### CLI

```bash
# Single check — auto-detects domain vs URL vs IP
sec-mcp check https://example.com
sec-mcp check malicious-domain.com
sec-mcp check 192.168.1.1

# Type-specific checks
sec-mcp check-domain example.com
sec-mcp check-url https://example.com/path
sec-mcp check-ip 192.168.1.1

# Batch check from a file (one value per line)
sec-mcp batch urls.txt

# Status, updates, sampling and cache control
sec-mcp status
sec-mcp update
sec-mcp sample -n 20
sec-mcp flush-cache
```

Every command except `sample` accepts `--json` for machine-readable output.

### Python API

```python
from sec_mcp import SecMCP

client = SecMCP()          # optional: SecMCP(db_path="/path/to/mcp.db")
client.update()            # download + index the feeds (first run only)

# Single check — check() returns CheckResult(blacklisted, explanation)
result = client.check("https://example.com")
print(result.blacklisted, result.explanation)
# result.to_dict() -> {"is_safe": True, "explain": "Not blacklisted"}

# Type-specific checks
client.check_domain("example.com")
client.check_url("https://example.com/path")
client.check_ip("192.168.1.1")

# Batch check
urls = ["https://example.com", "https://test.com", "192.168.1.1"]
for value, r in zip(urls, client.check_batch(urls)):
    print(f"{value}: {'BLOCKED' if r.blacklisted else 'SAFE'}")

# Status — StatusInfo(entry_count, last_update, sources, server_status)
status = client.get_status()
print(status.entry_count, status.last_update, client.scheduler_alive())
```

### MCP Server

sec-mcp runs as a stdio MCP server for AI/LLM integration (Claude Desktop, Cursor, Windsurf, …). `server.json` at the repo root ships the matching MCP Registry entry (`io.github.montimage/sec-mcp`).

1. Install `uv` (provides `uvx`): see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/), or `pip install uv`.
2. Populate the blacklist once:
   ```bash
   uvx --from sec-mcp sec-mcp update
   ```
3. Configure your MCP client (e.g. `claude_desktop_config.json`):
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

   > **How it works**: `uvx` downloads the `sec-mcp` package from PyPI and runs its
   > `sec-mcp-server` entry point — no virtual environment or absolute Python path
   > required. Alternatively, `pip install sec-mcp` into any environment and use
   > `"command": "sec-mcp-server"` with no `args`.

#### MCP tools

| Tool                | Description                                                              |
|---------------------|--------------------------------------------------------------------------|
| `check_batch`       | Check multiple domains/URLs/IPs in one call                              |
| `get_status`        | Blacklist status: entry counts, per-source breakdown, `scheduler_alive`  |
| `update_blacklists` | Force an immediate update (rate limited; emits per-source progress)      |
| `get_diagnostics`   | Diagnostic info — modes: `summary`, `full`, `health`, `performance`, `sample` |
| `add_entry`         | Manually add a blacklist entry (URL/domain or IP, optional score)        |
| `remove_entry`      | Remove a blacklist entry by domain, URL or IP                            |

`update_blacklists` is rate limited to one forced update per `min_update_interval_seconds` (default 300 in `config.json`): a second call inside the window returns `{"updated": false, "reason": ...}` without starting downloads, and callers that supply a progress token receive one `notifications/progress` per source.

The `get_diagnostics` modes:

- **`summary`** (default): entry counts, sources and last update times
- **`full`**: complete diagnostic data including health, stats and performance
- **`health`**: database reachability and scheduler state only
- **`performance`**: lookup metrics and hit rates (v2 storage only)
- **`sample`**: random sample of blacklist entries (`sample_count` parameter, 1–100)

#### HTTP transport and the landing-page playground

`sec-mcp-server` speaks stdio by default. Add `--http` to serve MCP over
streamable HTTP instead, so a browser — including the live playground on the
[landing page](https://montimage.github.io/sec-mcp/) — can call the tools:

```bash
sec-mcp update                       # populate the database once
sec-mcp-server --http                # → http://127.0.0.1:8000/mcp
sec-mcp-server --http --host 0.0.0.0 --port 9000
```

- CORS allows the origins in `SEC_MCP_CORS_ORIGINS` (default: local Vite dev/preview
  on ports 3000/4173 and `https://montimage.github.io`); credentials are never allowed.
  `*` allows any origin and also disables DNS-rebinding protection.
- Set `SEC_MCP_HTTP_AUTH_TOKEN` to require `Authorization: Bearer <token>` on every
  request. Binding a non-loopback host (e.g. `--host 0.0.0.0`) without one generates
  a random token for that run and prints it with a `#token=…` fragment: append it to
  the landing-page URL and the playground connects with it. Pass `--no-auth` to opt
  out (a warning is logged).

---

## Performance Optimization

Enable the in-memory v2 backend for dramatically faster lookups:

```bash
export MCP_USE_V2_STORAGE=true
```

### Measured results

Numbers below come from the bundled harness (`run_benchmark.sh`, see [Benchmarking](#benchmarking)):

| Operation        | v1 (Database) | v0.3.0 (Hybrid) | v0.4.0+ (Optimized) | Speedup (vs v1) |
|------------------|---------------|-----------------|---------------------|-----------------|
| Domain check     | 10 ms         | 0.01 ms         | **0.006 ms**        | **~1,600x**     |
| URL check        | 5 ms          | 0.001 ms        | **0.0007 ms**       | **~7,000x**     |
| IP + CIDR check  | 200 ms        | 0.01 ms         | **0.007 ms**        | **~28,000x**    |
| Batch 100 items  | 2–3 s         | 50–100 ms       | **50–100 ms**       | **~30x**        |

### Memory usage

- **v1 (default)**: ~10 MB (database on disk)
- **v2**: ~40–80 MB in-memory, depending on feed size

### How v2 is fast

1. **One in-memory index per entry type** — O(1) hash lookups over single domain/URL/IP indexes; reload builds a scratch index and swaps it under the lock, so readers never block and always see a complete snapshot.
2. **URL normalization** — `HTTP://EVIL.COM/` → `http://evil.com`; tracking parameters (`utm_*`, `fbclid`, …) stripped. One canonicalizer shared by both backends means identical verdicts.
3. **Integer IPv4 storage** — 4 bytes per IP instead of 13+ as a string.
4. **CIDR matching** — `pytricia` when the `fast-cidr` extra is installed, pure-Python `ipaddress` otherwise.

### Monitoring performance

```python
# v2 storage only — the get_diagnostics MCP tool exposes the same data
metrics = client.storage.get_metrics()
# {"total_lookups": ..., "cache_hits": ..., "hit_rate": ...,
#  "avg_lookup_time_ms": ..., "memory_usage_mb": ..., "using_pytricia": ...}
```

### Rollback to v1

```bash
export MCP_USE_V2_STORAGE=false   # or unset MCP_USE_V2_STORAGE
```

---

## Benchmarking

Compare storage backends with the bundled harness (requires `pip install "sec-mcp[fast-cidr]"` for the full comparison; `psutil` ships with sec-mcp):

```bash
./run_benchmark.sh --quick            # 10K entries, ~30 s
./run_benchmark.sh                    # 50K entries, ~2 min
./run_benchmark.sh --full --memory    # 100K entries + memory profiling
./run_benchmark.sh --v1 --v2opt       # compare specific versions
./run_benchmark.sh --all              # all versions
```

| Flag      | Description                                            |
|-----------|--------------------------------------------------------|
| `--quick` | Quick benchmark — 10K entries, 500 iterations          |
| `--full`  | Full benchmark — 100K entries, 1000 iterations         |
| `--all`   | Compare all versions (v1, v0.3.0, v0.4.0+)             |
| `--v1`    | Database-only storage                                  |
| `--v2`    | Hybrid storage                                         |
| `--v2opt` | Optimized hybrid storage                               |
| `--memory`| Include memory profiling (requires psutil)             |

Methodology and expected output: [BENCHMARK_PLAYBOOK.md](BENCHMARK_PLAYBOOK.md).

---

## Configuration

### Environment variables

| Variable                | Description                                                | Default                        |
|-------------------------|------------------------------------------------------------|--------------------------------|
| `MCP_DB_PATH`           | Custom SQLite database location                            | Platform-specific (see below)  |
| `MCP_USE_V2_STORAGE`    | `true` selects the in-memory `HybridStorage` backend       | `false` (v1 storage)           |
| `MCP_LOG_PATH`          | Log file location                                          | platformdirs log dir           |
| `MCP_CACHE_DIR`         | Feed download cache directory                              | platformdirs cache dir         |
| `MCP_DISABLE_SCHEDULER` | Set to `1` to not start the daily-update scheduler thread  | unset (scheduler runs)         |
| `SEC_MCP_CORS_ORIGINS`  | Comma-separated CORS origins for `sec-mcp-server --http`; `*` = any | local Vite ports + GitHub Pages |
| `SEC_MCP_HTTP_AUTH_TOKEN` | Bearer token required by `sec-mcp-server --http`         | unset (generated per run on a non-loopback host) |

### Default database locations

- **macOS**: `~/Library/Application Support/sec-mcp/mcp.db`
- **Linux**: `~/.local/share/sec-mcp/mcp.db`
- **Windows**: `%APPDATA%\sec-mcp\mcp.db`

### Configuration file

The shipped [`sec_mcp/config.json`](sec_mcp/config.json) controls feed sources, the update schedule and feed-safety bounds:

```json
{
  "blacklist_sources": { "OpenPhish": "...", "PhishStats": "...", "URLhaus": "...", "...": "10 feeds total" },
  "update_time": "00:00",
  "min_update_interval_seconds": 300,
  "cache_size": 10000,
  "max_feed_bytes": 67108864,
  "min_feed_entries": 1,
  "max_feed_entries": 500000,
  "max_range_addresses": 65536,
  "log_level": "INFO"
}
```

`update_time` sets the daily update hour, `min_update_interval_seconds` rate-limits forced updates, `cache_size` bounds the v1 positive-hit LRU, and the `max_*`/`min_*` keys bound accepted feed sizes.

---

## Project Structure

```
sec-mcp/
├── sec_mcp/                  # The package
│   ├── __init__.py           # Public API: SecMCP, CheckResult, StatusInfo, __version__
│   ├── sec_mcp.py            # SecMCP facade (check/check_batch/update/get_status/…)
│   ├── cli.py                # `sec-mcp` CLI (click)
│   ├── mcp_server.py         # Six MCP tools (SDK 2.x MCPServer)
│   ├── start_server.py       # `sec-mcp-server` entry point (stdio, or --http)
│   ├── http_transport.py     # Streamable-HTTP app: CORS, DNS-rebinding, bearer auth
│   ├── storage.py            # Backend selector + v1 database-only storage
│   ├── storage_queries.py    # v1 read/query half
│   ├── storage_base.py       # Shared schema, DB-path resolution, normalize_url
│   ├── storage_v2.py         # v2 HybridStorage (in-memory indexes + metrics)
│   ├── storage_v2_db.py      # v2 persistence layer (all SQLite access)
│   ├── storage_v2_index.py   # v2 in-memory indexes + CIDR matching
│   ├── storage_v2_writes.py  # v2 write path (persistence + rollback)
│   ├── storage_v2_stats.py   # v2 stats/reporting mixin
│   ├── feed_parsers.py       # One parser per blacklist feed source
│   ├── update_blacklist.py   # Feed download, scheduling and ingestion
│   ├── utility.py            # Validation, logging, config
│   ├── config.json           # Shipped defaults (sources, schedule, bounds)
│   └── tests/                # pytest suite (pytest.ini sets testpaths)
├── docs/                     # ARCHITECTURE, DEVELOPMENT, DEPLOYMENT, agent-env, playbook, decisions/, archive/
├── scripts/                  # check_test_baseline.sh (CI floor gate)
├── .github/                  # CI + PyPI + landing workflows, issue & PR templates
├── benchmark.py              # Benchmark script
├── run_benchmark.sh          # Benchmark helper
├── server.json               # MCP Registry metadata
├── react-landing-page/       # Standalone Vite site (not part of the package)
├── CONTRIBUTING.md           # Dev setup, tests, conventions, PR process
├── CODE_OF_CONDUCT.md        # Contributor Covenant
├── SECURITY.md               # Vulnerability reporting policy
├── CHANGELOG.md              # Release history (Keep a Changelog)
├── LICENSE                   # Apache-2.0
└── README.md                 # This file
```

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Design overview: components, storage backends, check semantics, MCP layer |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Dev-workflow hub: setup, repo layout, CI gates, conventions |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | PyPI release flow, end-user MCP-server deployment, landing-page deploy |
| [docs/agent-env.md](docs/agent-env.md) | Toolchain, environment variables, probe isolation |
| [docs/playbook.md](docs/playbook.md) | Top-10 usage cookbook for MCP clients |
| [docs/decisions/](docs/decisions/) | Architecture decision records (ADRs) |
| [BENCHMARK_PLAYBOOK.md](BENCHMARK_PLAYBOOK.md) | Benchmark methodology and interpretation |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, test/lint/coverage commands, branch & PR conventions |
| [SECURITY.md](SECURITY.md) | Supported versions and private vulnerability reporting |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev setup (`uv sync` is the single install command), test and lint commands, and the branch/commit/PR conventions. All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md), and security issues should be reported privately per [SECURITY.md](SECURITY.md).

- **Issues**: [GitHub Issues](https://github.com/Montimage/sec-mcp/issues) — bug report and feature request templates provided
- **Email**: contact@montimage.eu
- **Website**: https://www.montimage.eu

---

## Related Publications

No publications referencing sec-mcp are known yet. If you use sec-mcp in academic work, talks or blog posts, please [open an issue](https://github.com/Montimage/sec-mcp/issues) so we can list it here.

---

## License

[Apache License 2.0](LICENSE) — Copyright 2026 [Montimage](https://www.montimage.eu).

---

## Acknowledgments

- Threat-intelligence providers: OpenPhish, PhishStats, URLhaus, PhishTank, Spamhaus, Dshield, CINSSCORE, EmergingThreats, FeodoTracker and BlocklistDE
- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) Python SDK
- Powered by Python, SQLite, Click and httpx
