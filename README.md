# sec-mcp: Security Checking Toolkit

<!-- mcp-name: io.github.montimage/sec-mcp -->

A Python toolkit providing security checks for domains, URLs, IPs, and more. Integrate easily into any Python application, use via terminal CLI, or run as an MCP server to enrich LLM context with real-time threat insights.

Developed by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions.

<p align="left">
   <a href="https://pepy.tech/projects/sec-mcp"><img src="https://static.pepy.tech/badge/sec-mcp" alt="PyPI Downloads"></a>
   <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/v/sec-mcp.svg?label=PyPI&color=blue" alt="PyPI"></a>
   <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/pyversions/sec-mcp.svg?label=Python&color=informational" alt="Python Versions"></a>
   <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
</p>

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [CLI Usage](#cli-usage)
  - [Python API](#python-api)
  - [MCP Server](#mcp-server)
- [Performance Optimization](#-performance-optimization)
- [Benchmarking](#benchmarking)
- [Configuration](#configuration)
- [Development](#development)
- [License](#license)

---

## Features

- **Comprehensive Security Checks**: Validate domains, URLs, and IP addresses against multiple blacklist feeds
- **Multiple Threat Sources**: OpenPhish, PhishTank, PhishStats, URLhaus, BlocklistDE, CINSSCORE, and more
- **High Performance**: Ultra-fast in-memory storage with 1000-20,000x speedup over database-only approach
- **Smart Optimizations**: One O(1) in-memory index per entry type, URL normalization, and integer IPv4 storage for maximum efficiency
- **Flexible Integration**: Use as Python library, CLI tool, or MCP server for LLM integration
- **Thread-Safe**: SQLite storage with WAL mode and in-memory caching for concurrent operations
- **Auto-Updates**: Scheduled daily updates from threat intelligence sources
- **Rich Monitoring**: Built-in metrics, health checks, and performance tracking

---

## Installation

```bash
pip install sec-mcp
```

### Requirements

- Python 3.11 or newer (CI tests 3.11–3.14)
- SQLite 3
- Optional: `pytricia` (via `pip install "sec-mcp[fast-cidr]"`) for fast CIDR matching and benchmarking; without it a pure-Python `ipaddress` matcher is used

---

## Quick Start

1. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate.bat
   ```

2. **Install sec-mcp**:
   ```bash
   pip install sec-mcp
   ```

3. **Initialize and update the database**:
   ```bash
   sec-mcp update
   ```

4. **Check the status**:
   ```bash
   sec-mcp status
   ```

5. **Check a URL**:
   ```bash
   sec-mcp check https://example.com
   ```

---

## Usage

### CLI Usage

#### Single Check
```bash
sec-mcp check https://example.com
sec-mcp check malicious-domain.com
sec-mcp check 192.168.1.1

# Type-specific checks
sec-mcp check-domain example.com
sec-mcp check-url https://example.com/path
sec-mcp check-ip 192.168.1.1
```

All commands except `sample` accept `--json` for machine-readable output.

#### Batch Check
```bash
# From a file (one URL/domain/IP per line)
sec-mcp batch urls.txt

# Machine-readable results
sec-mcp batch urls.txt --json
```

#### Status and Updates
```bash
# Check blacklist status
sec-mcp status

# Update blacklists
sec-mcp update

# Sample stored entries
sec-mcp sample -n 20

# Clear the in-memory cache (reloads from the database)
sec-mcp flush-cache
```

### Python API

```python
from sec_mcp import SecMCP

# Initialize client
client = SecMCP()

# Update database (run once after installation)
client.update()

# Single check — check() returns a CheckResult(blacklisted, explanation)
result = client.check("https://example.com")
print(f"Blacklisted: {result.blacklisted}")
print(f"Explanation: {result.explanation}")
# result.to_dict() -> {"is_safe": True, "explain": "Not blacklisted"}

# Type-specific checks
client.check_domain("example.com")
client.check_url("https://example.com/path")
client.check_ip("192.168.1.1")

# Batch check
urls = ["https://example.com", "https://test.com", "192.168.1.1"]
results = client.check_batch(urls)
for value, r in zip(urls, results):
    print(f"{value}: {'BLOCKED' if r.blacklisted else 'SAFE'}")

# Get status — StatusInfo(entry_count, last_update, sources, server_status)
status = client.get_status()
print(f"Total entries: {status.entry_count}")
print(f"Last update: {status.last_update}")
print(f"Scheduler alive: {client.scheduler_alive()}")
```

### MCP Server

sec-mcp can run as an MCP server for AI/LLM integration (e.g., Claude, Windsurf, Cursor).

#### Setup

1. **Install `uv`** (provides `uvx`): see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/), or `pip install uv`.

2. **Update the blacklist**:
   ```bash
   uvx --from sec-mcp sec-mcp update
   ```

3. **Configure your MCP client** (e.g., `claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "sec-mcp": {
         "command": "uvx",
         "args": ["--from", "sec-mcp", "sec-mcp-server"],
         "env": {
           "MCP_USE_V2_STORAGE": "true"
         }
       }
     }
   }
   ```

   > **How it works**: `uvx` downloads the `sec-mcp` package from PyPI and runs its
   > `sec-mcp-server` entry point — no virtual environment or absolute Python path
   > required. Alternatively, `pip install sec-mcp` into any environment and use
   > `"command": "sec-mcp-server"` with no `args`.

#### Available MCP Tools

| Tool Name              | Description                                                                           |
|-----------------------|---------------------------------------------------------------------------------------|
| `check_batch`         | Check multiple domains/URLs/IPs in one call                                           |
| `get_status`          | Get blacklist status including entry counts and per-source breakdown                  |
| `update_blacklists`   | Force immediate update of all blacklists                                              |
| `get_diagnostics`     | Get diagnostic info with modes: summary, full, health, performance, sample            |
| `add_entry`           | Manually add a blacklist entry                                                        |
| `remove_entry`        | Remove a blacklist entry by URL or IP address                                         |

**Note**: The tools have been optimized to reduce token usage while maintaining full functionality. The `get_diagnostics` tool consolidates multiple monitoring functions with different modes.

`update_blacklists` is rate limited to one forced update per `min_update_interval_seconds` (default 300 in `config.json`): a second call inside the window returns `{"updated": false, "reason": ...}` without starting downloads, and callers that supply a progress token receive one `notifications/progress` per source. `get_status` and `get_diagnostics` report the real `scheduler_alive` thread state.

All six tools declare a typed return model, so `tools/list` exposes an `outputSchema` for each and call results carry `structuredContent` alongside the serialized text `content` (older clients keep working unchanged). `check_batch` items report a tri-state `verdict` (`safe` / `blacklisted` / `invalid`), and tool failures surface as `isError: true` results rather than connection errors.

#### Diagnostics Tool Modes

The `get_diagnostics` tool provides flexible monitoring with the following modes:

- **`summary`** (default): Entry counts, sources, and last update times
- **`full`**: Complete diagnostic data including health, stats, and performance
- **`health`**: Database and scheduler health status only
- **`performance`**: Performance metrics and hit rates (v2 storage only)
- **`sample`**: Random sample of blacklist entries (use `sample_count` parameter)

Example usage:
```python
# Get basic summary
await get_diagnostics()

# Check system health
await get_diagnostics(mode="health")

# Get performance metrics
await get_diagnostics(mode="performance")

# Sample 20 entries
await get_diagnostics(mode="sample", sample_count=20)
```

---

## 🚀 Performance Optimization

### High-Performance Mode (v0.3.0+)

Enable ultra-fast in-memory storage for dramatic performance improvements:

```bash
export MCP_USE_V2_STORAGE=true
```

### Performance Comparison

| Operation | v1 (Database) | v0.3.0 (Hybrid) | v0.4.0 (Optimized) | Speedup (vs v1) |
|-----------|---------------|-----------------|-------------------|-----------------|
| Domain check | 10ms | 0.01ms | **0.006ms** | **1,600x** |
| URL check | 5ms | 0.001ms | **0.0007ms** | **7,000x** |
| IP + CIDR check | 200ms | 0.01ms | **0.007ms** | **28,000x** |
| Batch 100 items | 2-3s | 50-100ms | **50-100ms** | **30x** |

### Memory Usage

- **v1 (default)**: ~10MB (database on disk)
- **v0.3.0 (v2)**: ~60-80MB (in-memory for 125K entries)
- **v0.4.0 (v2 optimized)**: **~40-50MB** (in-memory for 450K entries) - **30-40% reduction!**

### v0.4.0 Optimizations

1. **One In-Memory Index Per Entry Type**:
   - O(1) hash lookups over a single index each for domains, URLs and IPs
   - Snapshot swap on reload: readers always see a complete table

2. **URL Normalization**:
   - Automatically catches variations: `HTTP://EVIL.COM/` → `http://evil.com`
   - Removes tracking parameters: `?utm_source=spam`, `?fbclid=123`
   - One canonicalization shared by both backends — identical verdicts

3. **Integer IPv4 Storage**:
   - 4 bytes per IP (vs 13+ bytes as string)
   - 5-10% faster comparisons
   - ~1-2MB memory savings

### Monitoring Performance

```python
# Via the Python API (v2 storage only — get_diagnostics exposes the same data over MCP)
metrics = client.storage.get_metrics()

# Returns:
{
  "total_lookups": 1234,
  "domain_lookups": 567,
  "url_lookups": 432,
  "ip_lookups": 235,
  "cache_hits": 1100,
  "cache_misses": 134,
  "hit_rate": 0.89,
  "avg_lookup_time_ms": "0.0123",
  "memory_usage_mb": "45.3",
  "entry_count": 450000,
  "using_pytricia": true,
  "urls_normalized": 312,
  "ips_as_integers": 45000
}
```

### Rollback to v1

```bash
unset MCP_USE_V2_STORAGE
# or
export MCP_USE_V2_STORAGE=false
```

---

## Benchmarking

### Running Benchmarks

Compare performance across different storage implementations:

```bash
# Install dependencies (psutil ships with sec-mcp; pytricia is the fast-cidr extra)
pip install "sec-mcp[fast-cidr]"

# Quick benchmark (10K entries, ~30 seconds)
./run_benchmark.sh --quick

# Standard benchmark (50K entries, ~2 minutes)
./run_benchmark.sh

# Full benchmark (100K entries, ~5 minutes)
./run_benchmark.sh --full --memory

# Compare specific versions
./run_benchmark.sh --v1 --v2opt    # Compare v1 vs v0.4.0
./run_benchmark.sh --all           # Compare all versions
```

### Benchmark Options

| Flag | Description |
|------|-------------|
| `--quick` | Quick benchmark with 10K entries (500 iterations) |
| `--full` | Full benchmark with 100K entries (1000 iterations) |
| `--all` | Compare all versions (v1, v0.3.0, v0.4.0) |
| `--v1` | Benchmark v1 (database-only storage) |
| `--v2` | Benchmark v0.3.0 (hybrid storage) |
| `--v2opt` | Benchmark v0.4.0 (optimized hybrid storage) |
| `--memory` | Include memory profiling (requires psutil) |

### Example Output

```
BENCHMARK RESULTS COMPARISON
================================================================================
Operation                 v1 (DB)         v0.3.0 (Hybrid)      v0.4.0 (Optimized)   Speedup
----------------------------------------------------------------------------------------------------
domain_lookup             9.8234ms        0.0098ms             0.0059ms             1,664x
url_lookup                4.5632ms        0.0009ms             0.0007ms             6,519x
ip_lookup                 198.2341ms      0.0103ms             0.0071ms             27,920x
batch_100                 2453.21ms       87.45ms              72.31ms              33.9x

v0.4.0 OPTIMIZATION METRICS
================================================================================
Domain Lookup             Hot source hit rate: 100.0%
URL Lookup                Hot source hit rate: 98.9%
IP Lookup                 Hot source hit rate: 88.9%
```

For detailed benchmarking instructions and methodology, see [BENCHMARK_PLAYBOOK.md](BENCHMARK_PLAYBOOK.md).

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_DB_PATH` | Custom database location | Platform-specific (see below) |
| `MCP_USE_V2_STORAGE` | Enable high-performance mode | `false` |
| `MCP_LOG_PATH` | Log file location | platformdirs log dir |
| `MCP_CACHE_DIR` | Feed download cache directory | platformdirs cache dir |
| `MCP_DISABLE_SCHEDULER` | Set to `1` to not start the daily-update scheduler thread | unset (scheduler runs) |

### Default Database Locations

- **macOS**: `~/Library/Application Support/sec-mcp/mcp.db`
- **Linux**: `~/.local/share/sec-mcp/mcp.db`
- **Windows**: `%APPDATA%\sec-mcp\mcp.db`

### Custom Database Path

```bash
export MCP_DB_PATH=/path/to/custom/location/mcp.db
```

### Configuration File

The shipped `sec_mcp/config.json` controls feed sources, the update schedule and feed-safety bounds:

```json
{
  "blacklist_sources": {
    "OpenPhish": "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt",
    "PhishStats": "https://phishstats.info/phish_score.csv",
    "URLhaus": "https://urlhaus.abuse.ch/downloads/text/",
    "PhishTank": "https://data.phishtank.com/data/online-valid.csv",
    "SpamhausDROP": "https://www.spamhaus.org/drop/drop.txt",
    "Dshield": "https://www.dshield.org/block.txt",
    "CINSSCORE": "https://cinsscore.com/list/ci-badguys.txt",
    "EmergingThreats": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
    "FeodoTracker": "https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt",
    "BlocklistDE": "https://lists.blocklist.de/lists/all.txt"
  },
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

`update_time` sets the daily update hour, `min_update_interval_seconds` rate-limits forced updates, and the `max_*`/`min_*` keys bound accepted feed sizes.

---

## Development

### Setup Development Environment

Requires Python ≥3.11 and [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv` if needed).

```bash
# Clone repository
git clone https://github.com/montimage/sec-mcp.git
cd sec-mcp

# One dev-install command — creates .venv, installs the package
# editable plus the dev group (pytest, pytest-asyncio, pytest-cov,
# ruff, pytricia), pinned by uv.lock
uv sync
```

That is the whole setup: `uv sync` is the single dev-install command, and it works in a clean container too — verified in `docker run --rm -it python:3.13` with `pip install uv && uv sync` (uv reads `.python-version` and fetches the pinned interpreter itself; pass `--python 3.13` to use the system one instead).

### Running Tests

```bash
# Run all tests (suite is fully green: 400 passed)
uv run pytest -q -p no:cacheprovider

# Lint
uv run ruff check .

# With coverage (CI enforces --cov-fail-under=98)
uv run pytest --cov=sec_mcp --cov-report=term --cov-fail-under=98 -q -p no:cacheprovider
```

The suite is hermetic — `sec_mcp/tests/conftest.py` points `MCP_DB_PATH`, `MCP_LOG_PATH` and `MCP_CACHE_DIR` at temp dirs and disables the scheduler, so tests leave no trace. Only ad-hoc probes that construct `SecMCP()`/`Storage`/`BlacklistUpdater` need `export MCP_DB_PATH="$(mktemp -d)/probe.db"` first — see `docs/agent-env.md`.

### Project Structure

```
sec-mcp/
├── sec_mcp/                # Main package
│   ├── __init__.py         # Public API: SecMCP, CheckResult, StatusInfo, __version__
│   ├── sec_mcp.py          # SecMCP client facade (check/check_batch/update/get_status)
│   ├── cli.py              # `sec-mcp` CLI (click)
│   ├── mcp_server.py       # MCP tool definitions (SDK 2.x MCPServer)
│   ├── start_server.py     # `sec-mcp-server` entry point
│   ├── storage.py          # Storage backend selector + v1 storage (database-only)
│   ├── storage_v2.py       # v2 HybridStorage (in-memory indexes + metrics)
│   ├── storage_base.py     # Shared schema, DB-path resolution, StorageProtocol, normalize_url
│   ├── storage_v2_db.py    # v2 persistence layer (SQLiteStore — all SQLite access)
│   ├── storage_v2_index.py # v2 in-memory indexes and CIDR matching (pytricia/fallback)
│   ├── storage_v2_writes.py# v2 write path (add/delete entries, persistence + rollback)
│   ├── storage_v2_stats.py # v2 stats/reporting mixin
│   ├── storage_queries.py  # v1 read/query half (StorageQueryMixin)
│   ├── feed_parsers.py     # One parser per blacklist feed source
│   ├── update_blacklist.py # Feed download, scheduling and ingestion
│   ├── utility.py          # Validation, logging, config
│   ├── config.json         # Shipped defaults (sources, schedule, feed bounds)
│   └── tests/              # pytest suite (pytest.ini sets testpaths)
├── scripts/                # check_test_baseline.sh (floor gate)
├── docs/                   # Project docs (agent-env.md, decisions/, archive/)
├── benchmark.py            # Benchmark script
├── run_benchmark.sh        # Benchmark helper script
├── react-landing-page/     # Standalone Vite site (not part of the package)
└── README.md               # This file
```

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## About Montimage

sec-mcp is developed and maintained by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions. Montimage provides innovative security tools and services to help organizations protect their digital assets and ensure the security of their networks.

### Support

- **Issues**: [GitHub Issues](https://github.com/montimage/sec-mcp/issues)
- **Email**: contact@montimage.eu
- **Website**: https://www.montimage.eu

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev setup, test commands, branch/commit conventions and the PR process — and [CHANGELOG.md](CHANGELOG.md) for release history.

---

## Acknowledgments

- Threat intelligence sources: OpenPhish, PhishTank, PhishStats, URLhaus, BlocklistDE, CINSSCORE, and others
- Built with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- Powered by Python and SQLite
