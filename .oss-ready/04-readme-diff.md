diff --git a/README.md b/.oss-ready/04-readme-draft.md
index 432b004..3ffafd7 100644
--- a/README.md
+++ b/.oss-ready/04-readme-draft.md
@@ -1,100 +1,115 @@
-# sec-mcp: Security Checking Toolkit
+# sec-mcp
 
 <!-- mcp-name: io.github.montimage/sec-mcp -->
 
-A Python toolkit providing security checks for domains, URLs, IPs, and more. Integrate easily into any Python application, use via terminal CLI, or run as an MCP server to enrich LLM context with real-time threat insights.
-
-Developed by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions.
+**Check domains, URLs and IP addresses against live security blacklists — as a Python library, a terminal CLI, or an MCP server that gives LLM agents real-time threat context.**
 
 <p align="left">
-   <a href="https://pepy.tech/projects/sec-mcp"><img src="https://static.pepy.tech/badge/sec-mcp" alt="PyPI Downloads"></a>
+   <a href="https://github.com/Montimage/sec-mcp/actions/workflows/ci.yml"><img src="https://github.com/Montimage/sec-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/v/sec-mcp.svg?label=PyPI&color=blue" alt="PyPI"></a>
    <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/pyversions/sec-mcp.svg?label=Python&color=informational" alt="Python Versions"></a>
+   <a href="https://pepy.tech/projects/sec-mcp"><img src="https://static.pepy.tech/badge/sec-mcp" alt="PyPI Downloads"></a>
    <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="Apache License 2.0"></a>
 </p>
 
+sec-mcp aggregates ten public threat-intelligence feeds into a local SQLite database and answers "is this domain/URL/IP malicious?" in microseconds. Use it inside any Python application, from the terminal with `sec-mcp`, or as a [Model Context Protocol](https://modelcontextprotocol.io/) server so tools like Claude Desktop, Cursor and Windsurf can screen indicators against real blacklist data.
+
+Developed by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions.
+
 ---
 
 ## Table of Contents
 
 - [Features](#features)
-- [Installation](#installation)
+- [Demo](#demo)
 - [Quick Start](#quick-start)
+- [Installation](#installation)
 - [Usage](#usage)
-  - [CLI Usage](#cli-usage)
+  - [CLI](#cli)
   - [Python API](#python-api)
   - [MCP Server](#mcp-server)
-- [Performance Optimization](#-performance-optimization)
+- [Performance Optimization](#performance-optimization)
 - [Benchmarking](#benchmarking)
 - [Configuration](#configuration)
-- [Development](#development)
+- [Project Structure](#project-structure)
+- [Documentation](#documentation)
+- [Contributing](#contributing)
+- [Related Publications](#related-publications)
 - [License](#license)
+- [Acknowledgments](#acknowledgments)
 
 ---
 
 ## Features
 
-- **Comprehensive Security Checks**: Validate domains, URLs, and IP addresses against multiple blacklist feeds
-- **Multiple Threat Sources**: OpenPhish, PhishTank, PhishStats, URLhaus, BlocklistDE, CINSSCORE, and more
-- **High Performance**: Ultra-fast in-memory storage with 1000-20,000x speedup over database-only approach
-- **Smart Optimizations**: One O(1) in-memory index per entry type, URL normalization, and integer IPv4 storage for maximum efficiency
-- **Flexible Integration**: Use as Python library, CLI tool, or MCP server for LLM integration
-- **Thread-Safe**: SQLite storage with WAL mode and in-memory caching for concurrent operations
-- **Auto-Updates**: Scheduled daily updates from threat intelligence sources
-- **Rich Monitoring**: Built-in metrics, health checks, and performance tracking
+- **Comprehensive security checks** — validate domains, URLs and IPv4/IPv6 addresses, with domain→URL cascade semantics (a blacklisted domain condemns its URLs and subdomains; a blacklisted URL does not condemn its domain) and CIDR-range matching for IPs
+- **Ten threat-intelligence feeds** — OpenPhish, PhishStats, URLhaus, PhishTank, Spamhaus DROP, Dshield, CINSSCORE, EmergingThreats, FeodoTracker and BlocklistDE
+- **Three interfaces, one engine** — Python API (`SecMCP`), Click CLI (`sec-mcp`), and a stdio MCP server (`sec-mcp-server`) exposing six typed tools
+- **Two storage backends** — default SQLite storage (v1), or an in-memory hybrid (v2, `MCP_USE_V2_STORAGE=true`) with O(1) per-type indexes; up to ~28,000x faster lookups than the database-only path on the bundled benchmark
+- **URL normalization** — one canonicalizer shared by both backends: lowercasing, default-scheme handling and tracking-parameter stripping (`utm_*`, `fbclid`, …), so URL variants share one verdict
+- **Safe feed ingestion** — HTTPS-only downloads bounded by `max_feed_bytes` and entry-count sanity checks; a failing feed never aborts the others
+- **Scheduled daily updates** — a `schedule` job refreshes feeds at `update_time`; forced updates are rate limited to one per `min_update_interval_seconds` (default 300 s)
+- **Concurrency-friendly** — SQLite in WAL mode with `synchronous=NORMAL`, a thread-local shared connection per check, and lock-free snapshot reads on the v2 backend
+- **Structured MCP output** — every tool publishes a typed `outputSchema`, results carry `structuredContent`, `check_batch` reports a tri-state verdict (`safe` / `blacklisted` / `invalid`), and domain failures surface as `isError` results instead of protocol crashes
+- **Observable** — `get_diagnostics` MCP tool (summary / full / health / performance / sample modes), real `scheduler_alive` reporting and per-source entry counts
 
 ---
 
-## Installation
+## Demo
+
+> **PLACEHOLDER — needs maintainer input before publishing.** The repository ships no
+> screenshot or demo assets today. Suggested: an asciinema recording of
+> `sec-mcp update` → `sec-mcp check <url>`, or a screenshot of the six MCP tools
+> inside Claude Desktop. Add the file under `docs/assets/` (e.g. `docs/assets/demo.gif`)
+> and replace this block with `![sec-mcp demo](docs/assets/demo.gif)`.
+
+---
+
+## Quick Start
+
+From zero to a verdict in under five minutes:
 
 ```bash
 pip install sec-mcp
+sec-mcp update                        # download + index the feeds (first run only)
+sec-mcp check https://example.com     # → Status: Safe / Blacklisted
+sec-mcp status                        # entry counts + per-source breakdown
 ```
 
-### Requirements
-
-- Python 3.11 or newer (CI tests 3.11–3.14)
-- SQLite 3
-- Optional: `pytricia` (via `pip install "sec-mcp[fast-cidr]"`) for fast CIDR matching and benchmarking; without it a pure-Python `ipaddress` matcher is used
+To run it as an MCP server instead, jump to [MCP Server](#mcp-server) — no install beyond `uvx` is needed.
 
 ---
 
-## Quick Start
+## Installation
 
-1. **Create a virtual environment** (recommended):
-   ```bash
-   python3 -m venv .venv
-   source .venv/bin/activate  # Windows: .venv\Scripts\activate.bat
-   ```
+```bash
+pip install sec-mcp
+```
 
-2. **Install sec-mcp**:
-   ```bash
-   pip install sec-mcp
-   ```
+### Requirements
 
-3. **Initialize and update the database**:
-   ```bash
-   sec-mcp update
-   ```
+- Python 3.11 or newer (CI tests 3.11–3.14)
+- SQLite 3 (bundled with Python)
+- Optional: `pytricia` via `pip install "sec-mcp[fast-cidr]"` for fast CIDR matching; without it a pure-Python `ipaddress` matcher is used (`pytricia` builds from source and needs a C compiler)
 
-4. **Check the status**:
-   ```bash
-   sec-mcp status
-   ```
+### From source
 
-5. **Check a URL**:
-   ```bash
-   sec-mcp check https://example.com
-   ```
+Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv` if needed):
+
+```bash
+git clone https://github.com/Montimage/sec-mcp.git
+cd sec-mcp
+uv sync    # creates .venv, installs the package editable + dev tools, pinned by uv.lock
+```
 
 ---
 
 ## Usage
 
-### CLI Usage
+### CLI
 
-#### Single Check
 ```bash
+# Single check — auto-detects domain vs URL vs IP
 sec-mcp check https://example.com
 sec-mcp check malicious-domain.com
 sec-mcp check 192.168.1.1
@@ -103,49 +118,30 @@ sec-mcp check 192.168.1.1
 sec-mcp check-domain example.com
 sec-mcp check-url https://example.com/path
 sec-mcp check-ip 192.168.1.1
-```
 
-All commands except `sample` accept `--json` for machine-readable output.
-
-#### Batch Check
-```bash
-# From a file (one URL/domain/IP per line)
+# Batch check from a file (one value per line)
 sec-mcp batch urls.txt
 
-# Machine-readable results
-sec-mcp batch urls.txt --json
-```
-
-#### Status and Updates
-```bash
-# Check blacklist status
+# Status, updates, sampling and cache control
 sec-mcp status
-
-# Update blacklists
 sec-mcp update
-
-# Sample stored entries
 sec-mcp sample -n 20
-
-# Clear the in-memory cache (reloads from the database)
 sec-mcp flush-cache
 ```
 
+Every command except `sample` accepts `--json` for machine-readable output.
+
 ### Python API
 
 ```python
 from sec_mcp import SecMCP
 
-# Initialize client
-client = SecMCP()
-
-# Update database (run once after installation)
-client.update()
+client = SecMCP()          # optional: SecMCP(db_path="/path/to/mcp.db")
+client.update()            # download + index the feeds (first run only)
 
-# Single check — check() returns a CheckResult(blacklisted, explanation)
+# Single check — check() returns CheckResult(blacklisted, explanation)
 result = client.check("https://example.com")
-print(f"Blacklisted: {result.blacklisted}")
-print(f"Explanation: {result.explanation}")
+print(result.blacklisted, result.explanation)
 # result.to_dict() -> {"is_safe": True, "explain": "Not blacklisted"}
 
 # Type-specific checks
@@ -155,40 +151,31 @@ client.check_ip("192.168.1.1")
 
 # Batch check
 urls = ["https://example.com", "https://test.com", "192.168.1.1"]
-results = client.check_batch(urls)
-for value, r in zip(urls, results):
+for value, r in zip(urls, client.check_batch(urls)):
     print(f"{value}: {'BLOCKED' if r.blacklisted else 'SAFE'}")
 
-# Get status — StatusInfo(entry_count, last_update, sources, server_status)
+# Status — StatusInfo(entry_count, last_update, sources, server_status)
 status = client.get_status()
-print(f"Total entries: {status.entry_count}")
-print(f"Last update: {status.last_update}")
-print(f"Scheduler alive: {client.scheduler_alive()}")
+print(status.entry_count, status.last_update, client.scheduler_alive())
 ```
 
 ### MCP Server
 
-sec-mcp can run as an MCP server for AI/LLM integration (e.g., Claude, Windsurf, Cursor).
+sec-mcp runs as a stdio MCP server for AI/LLM integration (Claude Desktop, Cursor, Windsurf, …). `server.json` at the repo root ships the matching MCP Registry entry (`io.github.montimage/sec-mcp`).
 
-#### Setup
-
-1. **Install `uv`** (provides `uvx`): see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/), or `pip install uv`.
-
-2. **Update the blacklist**:
+1. Install `uv` (provides `uvx`): see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/), or `pip install uv`.
+2. Populate the blacklist once:
    ```bash
    uvx --from sec-mcp sec-mcp update
    ```
-
-3. **Configure your MCP client** (e.g., `claude_desktop_config.json`):
+3. Configure your MCP client (e.g. `claude_desktop_config.json`):
    ```json
    {
      "mcpServers": {
        "sec-mcp": {
          "command": "uvx",
          "args": ["--from", "sec-mcp", "sec-mcp-server"],
-         "env": {
-           "MCP_USE_V2_STORAGE": "true"
-         }
+         "env": { "MCP_USE_V2_STORAGE": "true" }
        }
      }
    }
@@ -199,226 +186,128 @@ sec-mcp can run as an MCP server for AI/LLM integration (e.g., Claude, Windsurf,
    > required. Alternatively, `pip install sec-mcp` into any environment and use
    > `"command": "sec-mcp-server"` with no `args`.
 
-#### Available MCP Tools
+#### MCP tools
 
-| Tool Name              | Description                                                                           |
-|-----------------------|---------------------------------------------------------------------------------------|
-| `check_batch`         | Check multiple domains/URLs/IPs in one call                                           |
-| `get_status`          | Get blacklist status including entry counts and per-source breakdown                  |
-| `update_blacklists`   | Force immediate update of all blacklists                                              |
-| `get_diagnostics`     | Get diagnostic info with modes: summary, full, health, performance, sample            |
-| `add_entry`           | Manually add a blacklist entry                                                        |
-| `remove_entry`        | Remove a blacklist entry by URL or IP address                                         |
+| Tool                | Description                                                              |
+|---------------------|--------------------------------------------------------------------------|
+| `check_batch`       | Check multiple domains/URLs/IPs in one call                              |
+| `get_status`        | Blacklist status: entry counts, per-source breakdown, `scheduler_alive`  |
+| `update_blacklists` | Force an immediate update (rate limited; emits per-source progress)      |
+| `get_diagnostics`   | Diagnostic info — modes: `summary`, `full`, `health`, `performance`, `sample` |
+| `add_entry`         | Manually add a blacklist entry (URL/domain or IP, optional score)        |
+| `remove_entry`      | Remove a blacklist entry by domain, URL or IP                            |
 
-**Note**: The tools have been optimized to reduce token usage while maintaining full functionality. The `get_diagnostics` tool consolidates multiple monitoring functions with different modes.
+`update_blacklists` is rate limited to one forced update per `min_update_interval_seconds` (default 300 in `config.json`): a second call inside the window returns `{"updated": false, "reason": ...}` without starting downloads, and callers that supply a progress token receive one `notifications/progress` per source.
 
-`update_blacklists` is rate limited to one forced update per `min_update_interval_seconds` (default 300 in `config.json`): a second call inside the window returns `{"updated": false, "reason": ...}` without starting downloads, and callers that supply a progress token receive one `notifications/progress` per source. `get_status` and `get_diagnostics` report the real `scheduler_alive` thread state.
+The `get_diagnostics` modes:
 
-All six tools declare a typed return model, so `tools/list` exposes an `outputSchema` for each and call results carry `structuredContent` alongside the serialized text `content` (older clients keep working unchanged). `check_batch` items report a tri-state `verdict` (`safe` / `blacklisted` / `invalid`), and tool failures surface as `isError: true` results rather than connection errors.
-
-#### Diagnostics Tool Modes
-
-The `get_diagnostics` tool provides flexible monitoring with the following modes:
-
-- **`summary`** (default): Entry counts, sources, and last update times
-- **`full`**: Complete diagnostic data including health, stats, and performance
-- **`health`**: Database and scheduler health status only
-- **`performance`**: Performance metrics and hit rates (v2 storage only)
-- **`sample`**: Random sample of blacklist entries (use `sample_count` parameter)
-
-Example usage:
-```python
-# Get basic summary
-await get_diagnostics()
-
-# Check system health
-await get_diagnostics(mode="health")
-
-# Get performance metrics
-await get_diagnostics(mode="performance")
-
-# Sample 20 entries
-await get_diagnostics(mode="sample", sample_count=20)
-```
+- **`summary`** (default): entry counts, sources and last update times
+- **`full`**: complete diagnostic data including health, stats and performance
+- **`health`**: database reachability and scheduler state only
+- **`performance`**: lookup metrics and hit rates (v2 storage only)
+- **`sample`**: random sample of blacklist entries (`sample_count` parameter, 1–100)
 
 ---
 
-## 🚀 Performance Optimization
+## Performance Optimization
 
-### High-Performance Mode (v0.3.0+)
-
-Enable ultra-fast in-memory storage for dramatic performance improvements:
+Enable the in-memory v2 backend for dramatically faster lookups:
 
 ```bash
 export MCP_USE_V2_STORAGE=true
 ```
 
-### Performance Comparison
-
-| Operation | v1 (Database) | v0.3.0 (Hybrid) | v0.4.0 (Optimized) | Speedup (vs v1) |
-|-----------|---------------|-----------------|-------------------|-----------------|
-| Domain check | 10ms | 0.01ms | **0.006ms** | **1,600x** |
-| URL check | 5ms | 0.001ms | **0.0007ms** | **7,000x** |
-| IP + CIDR check | 200ms | 0.01ms | **0.007ms** | **28,000x** |
-| Batch 100 items | 2-3s | 50-100ms | **50-100ms** | **30x** |
+### Measured results
 
-### Memory Usage
+Numbers below come from the bundled harness (`run_benchmark.sh`, see [Benchmarking](#benchmarking)):
 
-- **v1 (default)**: ~10MB (database on disk)
-- **v0.3.0 (v2)**: ~60-80MB (in-memory for 125K entries)
-- **v0.4.0 (v2 optimized)**: **~40-50MB** (in-memory for 450K entries) - **30-40% reduction!**
+| Operation        | v1 (Database) | v0.3.0 (Hybrid) | v0.4.0+ (Optimized) | Speedup (vs v1) |
+|------------------|---------------|-----------------|---------------------|-----------------|
+| Domain check     | 10 ms         | 0.01 ms         | **0.006 ms**        | **~1,600x**     |
+| URL check        | 5 ms          | 0.001 ms        | **0.0007 ms**       | **~7,000x**     |
+| IP + CIDR check  | 200 ms        | 0.01 ms         | **0.007 ms**        | **~28,000x**    |
+| Batch 100 items  | 2–3 s         | 50–100 ms       | **50–100 ms**       | **~30x**        |
 
-### v0.4.0 Optimizations
+### Memory usage
 
-1. **One In-Memory Index Per Entry Type**:
-   - O(1) hash lookups over a single index each for domains, URLs and IPs
-   - Snapshot swap on reload: readers always see a complete table
+- **v1 (default)**: ~10 MB (database on disk)
+- **v2**: ~40–80 MB in-memory, depending on feed size
 
-2. **URL Normalization**:
-   - Automatically catches variations: `HTTP://EVIL.COM/` → `http://evil.com`
-   - Removes tracking parameters: `?utm_source=spam`, `?fbclid=123`
-   - One canonicalization shared by both backends — identical verdicts
+### How v2 is fast
 
-3. **Integer IPv4 Storage**:
-   - 4 bytes per IP (vs 13+ bytes as string)
-   - 5-10% faster comparisons
-   - ~1-2MB memory savings
+1. **One in-memory index per entry type** — O(1) hash lookups over single domain/URL/IP indexes; reload builds a scratch index and swaps it under the lock, so readers never block and always see a complete snapshot.
+2. **URL normalization** — `HTTP://EVIL.COM/` → `http://evil.com`; tracking parameters (`utm_*`, `fbclid`, …) stripped. One canonicalizer shared by both backends means identical verdicts.
+3. **Integer IPv4 storage** — 4 bytes per IP instead of 13+ as a string.
+4. **CIDR matching** — `pytricia` when the `fast-cidr` extra is installed, pure-Python `ipaddress` otherwise.
 
-### Monitoring Performance
+### Monitoring performance
 
 ```python
-# Via the Python API (v2 storage only — get_diagnostics exposes the same data over MCP)
+# v2 storage only — the get_diagnostics MCP tool exposes the same data
 metrics = client.storage.get_metrics()
-
-# Returns:
-{
-  "total_lookups": 1234,
-  "domain_lookups": 567,
-  "url_lookups": 432,
-  "ip_lookups": 235,
-  "cache_hits": 1100,
-  "cache_misses": 134,
-  "hit_rate": 0.89,
-  "avg_lookup_time_ms": "0.0123",
-  "memory_usage_mb": "45.3",
-  "entry_count": 450000,
-  "using_pytricia": true,
-  "urls_normalized": 312,
-  "ips_as_integers": 45000
-}
+# {"total_lookups": ..., "cache_hits": ..., "hit_rate": ...,
+#  "avg_lookup_time_ms": ..., "memory_usage_mb": ..., "using_pytricia": ...}
 ```
 
 ### Rollback to v1
 
 ```bash
-unset MCP_USE_V2_STORAGE
-# or
-export MCP_USE_V2_STORAGE=false
+export MCP_USE_V2_STORAGE=false   # or unset MCP_USE_V2_STORAGE
 ```
 
 ---
 
 ## Benchmarking
 
-### Running Benchmarks
-
-Compare performance across different storage implementations:
+Compare storage backends with the bundled harness (requires `pip install "sec-mcp[fast-cidr]"` for the full comparison; `psutil` ships with sec-mcp):
 
 ```bash
-# Install dependencies (psutil ships with sec-mcp; pytricia is the fast-cidr extra)
-pip install "sec-mcp[fast-cidr]"
-
-# Quick benchmark (10K entries, ~30 seconds)
-./run_benchmark.sh --quick
-
-# Standard benchmark (50K entries, ~2 minutes)
-./run_benchmark.sh
-
-# Full benchmark (100K entries, ~5 minutes)
-./run_benchmark.sh --full --memory
-
-# Compare specific versions
-./run_benchmark.sh --v1 --v2opt    # Compare v1 vs v0.4.0
-./run_benchmark.sh --all           # Compare all versions
+./run_benchmark.sh --quick            # 10K entries, ~30 s
+./run_benchmark.sh                    # 50K entries, ~2 min
+./run_benchmark.sh --full --memory    # 100K entries + memory profiling
+./run_benchmark.sh --v1 --v2opt       # compare specific versions
+./run_benchmark.sh --all              # all versions
 ```
 
-### Benchmark Options
-
-| Flag | Description |
-|------|-------------|
-| `--quick` | Quick benchmark with 10K entries (500 iterations) |
-| `--full` | Full benchmark with 100K entries (1000 iterations) |
-| `--all` | Compare all versions (v1, v0.3.0, v0.4.0) |
-| `--v1` | Benchmark v1 (database-only storage) |
-| `--v2` | Benchmark v0.3.0 (hybrid storage) |
-| `--v2opt` | Benchmark v0.4.0 (optimized hybrid storage) |
-| `--memory` | Include memory profiling (requires psutil) |
+| Flag      | Description                                            |
+|-----------|--------------------------------------------------------|
+| `--quick` | Quick benchmark — 10K entries, 500 iterations          |
+| `--full`  | Full benchmark — 100K entries, 1000 iterations         |
+| `--all`   | Compare all versions (v1, v0.3.0, v0.4.0+)             |
+| `--v1`    | Database-only storage                                  |
+| `--v2`    | Hybrid storage                                         |
+| `--v2opt` | Optimized hybrid storage                               |
+| `--memory`| Include memory profiling (requires psutil)             |
 
-### Example Output
-
-```
-BENCHMARK RESULTS COMPARISON
-================================================================================
-Operation                 v1 (DB)         v0.3.0 (Hybrid)      v0.4.0 (Optimized)   Speedup
-----------------------------------------------------------------------------------------------------
-domain_lookup             9.8234ms        0.0098ms             0.0059ms             1,664x
-url_lookup                4.5632ms        0.0009ms             0.0007ms             6,519x
-ip_lookup                 198.2341ms      0.0103ms             0.0071ms             27,920x
-batch_100                 2453.21ms       87.45ms              72.31ms              33.9x
-
-v0.4.0 OPTIMIZATION METRICS
-================================================================================
-Domain Lookup             Hot source hit rate: 100.0%
-URL Lookup                Hot source hit rate: 98.9%
-IP Lookup                 Hot source hit rate: 88.9%
-```
-
-For detailed benchmarking instructions and methodology, see [BENCHMARK_PLAYBOOK.md](BENCHMARK_PLAYBOOK.md).
+Methodology and expected output: [BENCHMARK_PLAYBOOK.md](BENCHMARK_PLAYBOOK.md).
 
 ---
 
 ## Configuration
 
-### Environment Variables
+### Environment variables
 
-| Variable | Description | Default |
-|----------|-------------|---------|
-| `MCP_DB_PATH` | Custom database location | Platform-specific (see below) |
-| `MCP_USE_V2_STORAGE` | Enable high-performance mode | `false` |
-| `MCP_LOG_PATH` | Log file location | platformdirs log dir |
-| `MCP_CACHE_DIR` | Feed download cache directory | platformdirs cache dir |
-| `MCP_DISABLE_SCHEDULER` | Set to `1` to not start the daily-update scheduler thread | unset (scheduler runs) |
+| Variable                | Description                                                | Default                        |
+|-------------------------|------------------------------------------------------------|--------------------------------|
+| `MCP_DB_PATH`           | Custom SQLite database location                            | Platform-specific (see below)  |
+| `MCP_USE_V2_STORAGE`    | `true` selects the in-memory `HybridStorage` backend       | `false` (v1 storage)           |
+| `MCP_LOG_PATH`          | Log file location                                          | platformdirs log dir           |
+| `MCP_CACHE_DIR`         | Feed download cache directory                              | platformdirs cache dir         |
+| `MCP_DISABLE_SCHEDULER` | Set to `1` to not start the daily-update scheduler thread  | unset (scheduler runs)         |
 
-### Default Database Locations
+### Default database locations
 
 - **macOS**: `~/Library/Application Support/sec-mcp/mcp.db`
 - **Linux**: `~/.local/share/sec-mcp/mcp.db`
 - **Windows**: `%APPDATA%\sec-mcp\mcp.db`
 
-### Custom Database Path
-
-```bash
-export MCP_DB_PATH=/path/to/custom/location/mcp.db
-```
-
-### Configuration File
+### Configuration file
 
-The shipped `sec_mcp/config.json` controls feed sources, the update schedule and feed-safety bounds:
+The shipped [`sec_mcp/config.json`](sec_mcp/config.json) controls feed sources, the update schedule and feed-safety bounds:
 
 ```json
 {
-  "blacklist_sources": {
-    "OpenPhish": "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt",
-    "PhishStats": "https://phishstats.info/phish_score.csv",
-    "URLhaus": "https://urlhaus.abuse.ch/downloads/text/",
-    "PhishTank": "https://data.phishtank.com/data/online-valid.csv",
-    "SpamhausDROP": "https://www.spamhaus.org/drop/drop.txt",
-    "Dshield": "https://www.dshield.org/block.txt",
-    "CINSSCORE": "https://cinsscore.com/list/ci-badguys.txt",
-    "EmergingThreats": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
-    "FeodoTracker": "https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt",
-    "BlocklistDE": "https://lists.blocklist.de/lists/all.txt"
-  },
+  "blacklist_sources": { "OpenPhish": "...", "PhishStats": "...", "URLhaus": "...", "...": "10 feeds total" },
   "update_time": "00:00",
   "min_update_interval_seconds": 300,
   "cache_size": 10000,
@@ -430,105 +319,98 @@ The shipped `sec_mcp/config.json` controls feed sources, the update schedule and
 }
 ```
 
-`update_time` sets the daily update hour, `min_update_interval_seconds` rate-limits forced updates, and the `max_*`/`min_*` keys bound accepted feed sizes.
+`update_time` sets the daily update hour, `min_update_interval_seconds` rate-limits forced updates, `cache_size` bounds the v1 positive-hit LRU, and the `max_*`/`min_*` keys bound accepted feed sizes.
 
 ---
 
-## Development
-
-### Setup Development Environment
-
-Requires Python ≥3.11 and [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv` if needed).
-
-```bash
-# Clone repository
-git clone https://github.com/montimage/sec-mcp.git
-cd sec-mcp
-
-# One dev-install command — creates .venv, installs the package
-# editable plus the dev group (pytest, pytest-asyncio, pytest-cov,
-# ruff, pytricia), pinned by uv.lock
-uv sync
-```
-
-That is the whole setup: `uv sync` is the single dev-install command, and it works in a clean container too — verified in `docker run --rm -it python:3.13` with `pip install uv && uv sync` (uv reads `.python-version` and fetches the pinned interpreter itself; pass `--python 3.13` to use the system one instead).
-
-### Running Tests
-
-```bash
-# Run all tests (suite is fully green: 400 passed)
-uv run pytest -q -p no:cacheprovider
-
-# Lint
-uv run ruff check .
-
-# With coverage (CI enforces --cov-fail-under=98)
-uv run pytest --cov=sec_mcp --cov-report=term --cov-fail-under=98 -q -p no:cacheprovider
-```
-
-The suite is hermetic — `sec_mcp/tests/conftest.py` points `MCP_DB_PATH`, `MCP_LOG_PATH` and `MCP_CACHE_DIR` at temp dirs and disables the scheduler, so tests leave no trace. Only ad-hoc probes that construct `SecMCP()`/`Storage`/`BlacklistUpdater` need `export MCP_DB_PATH="$(mktemp -d)/probe.db"` first — see `docs/agent-env.md`.
-
-### Project Structure
+## Project Structure
 
 ```
 sec-mcp/
-├── sec_mcp/                # Main package
-│   ├── __init__.py         # Public API: SecMCP, CheckResult, StatusInfo, __version__
-│   ├── sec_mcp.py          # SecMCP client facade (check/check_batch/update/get_status)
-│   ├── cli.py              # `sec-mcp` CLI (click)
-│   ├── mcp_server.py       # MCP tool definitions (SDK 2.x MCPServer)
-│   ├── start_server.py     # `sec-mcp-server` entry point
-│   ├── storage.py          # Storage backend selector + v1 storage (database-only)
-│   ├── storage_v2.py       # v2 HybridStorage (in-memory indexes + metrics)
-│   ├── storage_base.py     # Shared schema, DB-path resolution, StorageProtocol, normalize_url
-│   ├── storage_v2_db.py    # v2 persistence layer (SQLiteStore — all SQLite access)
-│   ├── storage_v2_index.py # v2 in-memory indexes and CIDR matching (pytricia/fallback)
-│   ├── storage_v2_writes.py# v2 write path (add/delete entries, persistence + rollback)
-│   ├── storage_v2_stats.py # v2 stats/reporting mixin
-│   ├── storage_queries.py  # v1 read/query half (StorageQueryMixin)
-│   ├── feed_parsers.py     # One parser per blacklist feed source
-│   ├── update_blacklist.py # Feed download, scheduling and ingestion
-│   ├── utility.py          # Validation, logging, config
-│   ├── config.json         # Shipped defaults (sources, schedule, feed bounds)
-│   └── tests/              # pytest suite (pytest.ini sets testpaths)
-├── scripts/                # check_test_baseline.sh (floor gate)
-├── docs/                   # Project docs (agent-env.md, decisions/, archive/)
-├── benchmark.py            # Benchmark script
-├── run_benchmark.sh        # Benchmark helper script
-├── react-landing-page/     # Standalone Vite site (not part of the package)
-└── README.md               # This file
+├── sec_mcp/                  # The package
+│   ├── __init__.py           # Public API: SecMCP, CheckResult, StatusInfo, __version__
+│   ├── sec_mcp.py            # SecMCP facade (check/check_batch/update/get_status/…)
+│   ├── cli.py                # `sec-mcp` CLI (click)
+│   ├── mcp_server.py         # Six MCP tools (SDK 2.x MCPServer)
+│   ├── start_server.py       # `sec-mcp-server` entry point (stdio)
+│   ├── storage.py            # Backend selector + v1 database-only storage
+│   ├── storage_queries.py    # v1 read/query half
+│   ├── storage_base.py       # Shared schema, DB-path resolution, normalize_url
+│   ├── storage_v2.py         # v2 HybridStorage (in-memory indexes + metrics)
+│   ├── storage_v2_db.py      # v2 persistence layer (all SQLite access)
+│   ├── storage_v2_index.py   # v2 in-memory indexes + CIDR matching
+│   ├── storage_v2_writes.py  # v2 write path (persistence + rollback)
+│   ├── storage_v2_stats.py   # v2 stats/reporting mixin
+│   ├── feed_parsers.py       # One parser per blacklist feed source
+│   ├── update_blacklist.py   # Feed download, scheduling and ingestion
+│   ├── utility.py            # Validation, logging, config
+│   ├── config.json           # Shipped defaults (sources, schedule, bounds)
+│   └── tests/                # pytest suite (pytest.ini sets testpaths)
+├── docs/                     # ARCHITECTURE, DEVELOPMENT, DEPLOYMENT, agent-env, playbook, decisions/, archive/
+├── scripts/                  # check_test_baseline.sh (CI floor gate)
+├── .github/                  # CI + PyPI + landing workflows, issue & PR templates
+├── benchmark.py              # Benchmark script
+├── run_benchmark.sh          # Benchmark helper
+├── server.json               # MCP Registry metadata
+├── react-landing-page/       # Standalone Vite site (not part of the package)
+├── CONTRIBUTING.md           # Dev setup, tests, conventions, PR process
+├── CODE_OF_CONDUCT.md        # Contributor Covenant
+├── SECURITY.md               # Vulnerability reporting policy
+├── CHANGELOG.md              # Release history (Keep a Changelog)
+├── LICENSE                   # Apache-2.0
+└── README.md                 # This file
 ```
 
 ---
 
-## License
-
-Apache License 2.0 - see [LICENSE](LICENSE) file for details. Copyright 2026 Montimage.
+## Documentation
+
+| Document | Contents |
+|----------|----------|
+| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Design overview: components, storage backends, check semantics, MCP layer |
+| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Dev-workflow hub: setup, repo layout, CI gates, conventions |
+| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | PyPI release flow, end-user MCP-server deployment, landing-page deploy |
+| [docs/agent-env.md](docs/agent-env.md) | Toolchain, environment variables, probe isolation |
+| [docs/playbook.md](docs/playbook.md) | Top-10 usage cookbook for MCP clients |
+| [docs/decisions/](docs/decisions/) | Architecture decision records (ADRs) |
+| [BENCHMARK_PLAYBOOK.md](BENCHMARK_PLAYBOOK.md) | Benchmark methodology and interpretation |
+| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, test/lint/coverage commands, branch & PR conventions |
+| [SECURITY.md](SECURITY.md) | Supported versions and private vulnerability reporting |
+| [CHANGELOG.md](CHANGELOG.md) | Release history |
 
 ---
 
-## About Montimage
-
-sec-mcp is developed and maintained by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions. Montimage provides innovative security tools and services to help organizations protect their digital assets and ensure the security of their networks.
+## Contributing
 
-### Support
+Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev setup (`uv sync` is the single install command), test and lint commands, and the branch/commit/PR conventions. All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md), and security issues should be reported privately per [SECURITY.md](SECURITY.md).
 
-- **Issues**: [GitHub Issues](https://github.com/montimage/sec-mcp/issues)
+- **Issues**: [GitHub Issues](https://github.com/Montimage/sec-mcp/issues) — bug report and feature request templates provided
 - **Email**: contact@montimage.eu
 - **Website**: https://www.montimage.eu
 
 ---
 
-## Contributing
+## Related Publications
+
+> **PLACEHOLDER — filled in by step 5 of the OSS-readiness flow.** Do not publish
+> this section as-is. Step 5 will insert Montimage papers, talks or blog posts
+> related to sec-mcp (e.g. threat-intelligence and network-monitoring
+> publications). If no publications apply, delete the whole section.
+
+<!-- STEP-5 TODO: add publication entries here, one bullet each:
+     - Author(s). "Title." Venue, Year. https://doi.org/... (or URL)
+-->
 
-Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev setup, test commands, branch/commit conventions and the PR process — and [CHANGELOG.md](CHANGELOG.md) for release history. All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
+---
+
+## License
 
-Further docs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (design and components), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) (dev workflow hub), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (PyPI release, MCP-server and landing-page deployment), [docs/playbook.md](docs/playbook.md) (usage cookbook).
+[Apache License 2.0](LICENSE) — Copyright 2026 [Montimage](https://www.montimage.eu).
 
 ---
 
 ## Acknowledgments
 
-- Threat intelligence sources: OpenPhish, PhishTank, PhishStats, URLhaus, BlocklistDE, CINSSCORE, and others
-- Built with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
-- Powered by Python and SQLite
+- Threat-intelligence providers: OpenPhish, PhishStats, URLhaus, PhishTank, Spamhaus, Dshield, CINSSCORE, EmergingThreats, FeodoTracker and BlocklistDE
+- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) Python SDK
+- Powered by Python, SQLite, Click and httpx
