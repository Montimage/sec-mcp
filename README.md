# sec-mcp: Security Checking Toolkit

A Python toolkit providing security checks for domains, URLs, IPs, and more. Integrate easily into any Python application, use via terminal CLI, or run as an MCP server to enrich LLM context with real-time threat insights.

Developed by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions.

<p align="left">
   <a href="https://pepy.tech/projects/sec-mcp"><img src="https://static.pepy.tech/badge/sec-mcp" alt="PyPI Downloads"></a>
   <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/v/sec-mcp.svg?label=PyPI&color=blue" alt="PyPI"></a>
   <a href="https://pypi.org/project/sec-mcp/"><img src="https://img.shields.io/pypi/pyversions/sec-mcp.svg?label=Python&color=informational" alt="Python Versions"></a>
   <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
</p>

## MCP Server & LLM Support

sec-mcp is designed for seamless integration with Model Context Protocol (MCP) compatible clients (e.g., Claude, Windsurf, Cursor) for real-time security checks in LLM workflows.

### Available MCP Tools

| Tool Name              | Signature / Endpoint            | Description                                                                           |
|-----------------------|---------------------------------|---------------------------------------------------------------------------------------|
| `check_blacklist`     | `check_blacklist(value: str)`   | Check a single value (domain, URL, or IP) against the blacklist.                      |
| `check_batch`         | `check_batch(values: List[str])`| Bulk check multiple domains/URLs/IPs in one call.                                     |
| `get_blacklist_status`| `get_blacklist_status()`        | Get status of the blacklist, including entry counts and per-source breakdown.         |
| `sample_blacklist`    | `sample_blacklist(count: int)`  | Return a random sample of blacklist entries.                                          |
| `get_source_stats`    | `get_source_stats()`            | Retrieve detailed stats: total entries, per-source counts, last update timestamps.    |
| `get_update_history`  | `get_update_history(...)`       | Fetch update history records, optionally filtered by source and time range.           |
| `flush_cache`         | `flush_cache()`                 | Clear the in-memory cache (or reload data for v2 storage).                            |
| `add_entry`           | `add_entry(url, ip, ...)`       | Manually add a blacklist entry.                                                       |
| `remove_entry`        | `remove_entry(value: str)`      | Remove a blacklist entry by URL or IP address.                                        |
| `update_blacklists`   | `update_blacklists()`           | Force immediate update of all blacklists.                                             |
| `health_check`        | `health_check()`                | Perform a health check of the database and scheduler.                                 |
| `get_storage_metrics` | `get_storage_metrics()` 🆕      | Get storage performance metrics (lookups, hit rate, memory usage). **v0.3.0+**        |

### MCP Server Setup

To run sec-mcp as an MCP server for AI-driven clients (e.g., Claude), follow these steps:

1. Create a virtual environment:
   ```bash
   python3.12 -m venv .venv
   ```

2. Activate the virtual environment:
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate.bat
   ```

3. Install sec-mcp:
   ```bash
   pip install sec-mcp
   ```

4. Verify the status:
   ```bash
   sec-mcp status
   ```

5. Update the blacklist database:
   ```bash
   sec-mcp update
   ```

6. Verify the database:
   ```bash
   sec-mcp status
   ```

7. Configure your MCP client (e.g., Claude, Windsurf, Cursor) to point at the command:
   ```json
   {
     "mcpServers": {
       "sec-mcp": {
         "command": "/absolute/path/to/.venv/bin/python",
         "args": ["-m", "sec_mcp.start_server"]
       }
     }
   }
   ```
   > **Important:**
   > - Use the absolute path to the Python executable in your virtual environment.
   > - For Windows, the path might look like: `C:\path\to\.venv\Scripts\python.exe`

8. The sec-mcp tools should now be available in your MCP client for checking URLs, domains, and IPs.

### 🚀 Performance Optimization (v0.3.0+)

**New in v0.3.0**: Ultra-fast in-memory storage for 1000-20,000x performance improvement!
**New in v0.4.0**: Data-driven optimizations for additional 30-50% speedup + 30-40% memory reduction!

#### Enable High-Performance Mode

For maximum performance, enable the optimized HybridStorage (v2):

```bash
export MCP_USE_V2_STORAGE=true
```

Then start the server as usual. On first start, it will load all blacklist data into memory (takes 5-10 seconds), after which all lookups are nearly instant.

#### Performance Comparison

| Operation | v1 (Database) | v0.3.0 (v2) | v0.4.0 (v2 optimized) | Speedup (vs v1) |
|-----------|---------------|-------------|----------------------|----------------|
| Domain check | 10ms | 0.01ms | **0.006ms** | **1,600x** |
| URL check | 5ms | 0.001ms | **0.0007ms** | **7,000x** |
| IP + CIDR check | 200ms | 0.01ms | **0.007ms** | **28,000x** |
| Batch 100 items | 2-3s | 50-100ms | **50-100ms** | **30x** |

#### v0.4.0 Optimizations

**Tiered Lookup (Hot/Cold Sources)**:
- Checks frequently-hit sources first for early exit
- 70-90% of lookups hit hot sources
- Based on production data analysis:
  - Hot URLs: PhishTank + URLhaus (74% of all URLs)
  - Hot IPs: BlocklistDE + CINSSCORE (90% of all IPs)

**URL Normalization**:
- Automatically catches variations: `HTTP://EVIL.COM/` → `http://evil.com`
- Removes tracking parameters: `?utm_source=spam`, `?fbclid=123`
- 15-25% memory reduction for URLs

**Integer IPv4 Storage**:
- 4 bytes per IP (vs 13+ bytes as string)
- 5-10% faster comparisons
- ~1-2MB memory savings

#### Memory Usage

- **v1 (default)**: ~10MB (database on disk)
- **v0.3.0 (v2)**: ~60-80MB (in-memory for 125K entries)
- **v0.4.0 (v2 optimized)**: **~40-50MB** (in-memory for 450K entries) - **30-40% reduction!**

The memory footprint is very reasonable on modern systems, and the performance gains are substantial.

#### Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "sec-mcp": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "sec_mcp.start_server"],
      "env": {
        "MCP_USE_V2_STORAGE": "true"
      }
    }
  }
}
```

#### Monitoring Performance

Use the new `get_storage_metrics` tool to monitor performance:

```python
# Via MCP tool
await get_storage_metrics()

# Returns:
{
  "total_lookups": 1234,
  "domain_lookups": 567,
  "url_lookups": 432,
  "ip_lookups": 235,
  "avg_lookup_time_ms": "0.0123",
  "memory_usage_mb": "67.3",
  "hit_rate": 0.89,
  "using_pytricia": true
}
```

#### Running Benchmarks

To compare performance across different storage versions, use the included benchmark script:

```bash
# Install required dependencies first
pip install pytricia psutil

# Quick benchmark (10K entries, ~30 seconds)
python benchmark.py --quick

# Standard benchmark (50K entries, ~2 minutes)
python benchmark.py

# Full benchmark (100K entries, production-like, ~5 minutes)
python benchmark.py --full --memory

# Compare specific versions
python benchmark.py --v2 --v2opt  # Compare v0.3.0 vs v0.4.0
python benchmark.py --all         # Compare all versions (v1, v0.3.0, v0.4.0)
```

The benchmark will output a comparison table showing:
- Lookup times for domains, URLs, IPs, and CIDR ranges
- Memory usage for each version
- Hot source hit rates (v0.4.0 optimization metrics)
- Overall speedup compared to v1

Example output:
```
BENCHMARK RESULTS COMPARISON
================================================================================
Operation                 v1 (DB)         v0.3.0 (Hybrid)      v0.4.0 (Optimized)   Speedup
----------------------------------------------------------------------------------------------------
domain_lookup             9.8234ms        0.0098ms             0.0059ms             1,664x
url_lookup                4.5632ms        0.0009ms             0.0007ms             6,519x
ip_lookup                 198.2341ms      0.0103ms             0.0071ms             27,920x
```

#### Rollback

To revert to v1 (database-only) storage:

```bash
unset MCP_USE_V2_STORAGE
# or
export MCP_USE_V2_STORAGE=false
```

---

## API Functions

| Function Name        | Signature                                             | Description                                                     |
|---------------------|------------------------------------------------------|-----------------------------------------------------------------|
| `check`             | `check(value: str) -> CheckResult`                   | Check a single domain, URL, or IP against the blacklist.        |
| `check_batch`       | `check_batch(values: List[str]) -> List[CheckResult]`| Batch check of multiple values.                                 |
| `check_ip`          | `check_ip(ip: str) -> CheckResult`                   | Check if an IP (or network) is blacklisted.                     |
| `check_domain`      | `check_domain(domain: str) -> CheckResult`           | Check if a domain (including parent domains) is blacklisted.    |
| `check_url`         | `check_url(url: str) -> CheckResult`                 | Check if a URL is blacklisted.                                  |
| `get_status`        | `get_status() -> StatusInfo`                         | Get current status of the blacklist service.                    |
| `update`            | `update() -> None`                                   | Force an immediate update of all blacklists.                    |
| `sample`            | `sample(count: int = 10) -> List[str]`               | Return a random sample of blacklist entries.                    |

---

## Features

- Comprehensive security checks for domains, URLs, IP addresses, and more against multiple blacklist feeds
- On-demand updates from OpenPhish, PhishStats, URLhaus and custom sources
- High-performance, thread-safe SQLite storage with in-memory caching for fast lookups
- Python API via `SecMCP` class for easy integration into your applications
- Intuitive Click-based CLI for interactive single or batch scans
- Built-in MCP server support for LLM/AI integrations over JSON/STDIO

---

## Environment Variable: MCP_DB_PATH

By default, sec-mcp stores its SQLite database (`mcp.db`) in a shared, cross-platform location:

- **macOS:** `~/Library/Application Support/sec-mcp/mcp.db`
- **Linux:** `~/.local/share/sec-mcp/mcp.db`
- **Windows:** `%APPDATA%\sec-mcp\mcp.db`

You can override this location by setting the `MCP_DB_PATH` environment variable:

```sh
export MCP_DB_PATH=/path/to/your/custom/location/mcp.db
```

Set this variable before running any sec-mcp commands or starting the server. The directory will be created if it does not exist.

## Installation

```bash
pip install sec-mcp
```

## Usage via CLI

1. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate.bat
   ```

2. Install the package:
   ```bash
   pip install sec-mcp
   ```

3. Verify the status:
   ```bash
   sec-mcp status
   ```

4. Populate the database with security data:
   ```bash
   sec-mcp update
   ```

5. Verify the database has been populated:
   ```bash
   sec-mcp status
   ```

6. Check a single URL/domain/IP:
   ```bash
   sec-mcp check https://example.com
   ```

7. Batch check from a file:
   ```bash
   sec-mcp batch urls.txt
   ```

## Usage via API (Python)

1. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate.bat
   ```

2. Install in your project:
   ```bash
   pip install sec-mcp
   ```

3. Import, initialize, and update the database:
   ```python
   from sec_mcp import SecMCP

   client = SecMCP()

   # Populate the database with security data (run once after installation)
   client.update()
   ```

4. Single check:
   ```python
   result = client.check("https://example.com")
   print(result.to_json())
   ```

5. Batch check:
   ```python
   urls = ["https://example.com", "https://test.com"]
   results = client.check_batch(urls)
   for r in results:
       print(r.to_json())
   ```

## Usage via MCP Client

To run sec-mcp as an MCP server for AI-driven clients (e.g., Claude):

1. Create a virtual environment:
   ```bash
   python3.12 -m venv .venv
   ```

2. Activate the virtual environment:
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate.bat
   ```

3. Install sec-mcp:
   ```bash
   pip install sec-mcp
   ```

4. Verify the status:
   ```bash
   sec-mcp status
   ```

5. Update the blacklist database:
   ```bash
   sec-mcp update
   ```

6. Verify the database:
   ```bash
   sec-mcp status
   ```

7. Configure your MCP client (e.g., Claude, Windsurf, Cursor) with:
   ```json
   {
     "mcpServers": {
       "sec-mcp": {
         "command": "/absolute/path/to/.venv/bin/python",
         "args": ["-m", "sec_mcp.start_server"]
       }
     }
   }
   ```
   > **Note:**
   > - Use the absolute path to the Python executable in your virtual environment.
   > - For Windows, the path might look like: `C:\path\to\.venv\Scripts\python.exe`

8. The sec-mcp tools should now be available in your MCP client.

## New MCP Server Tools

The following RPC endpoints are now available:

- **check_batch(values: List[str])**: Bulk check multiple domains/URLs/IPs in one call. Returns a list of `{ value, is_safe, explanation }`.
- **sample_blacklist(count: int)**: Return a random sample of blacklist entries for quick inspection.
- **get_source_stats()**: Retrieve detailed stats: total entries, per-source counts, and last update timestamps. Returns `{ total_entries, per_source, last_updates }`.
- **get_update_history(source?: str, start?: str, end?: str)**: Fetch update history records, optionally filtered by source and time range.
- **flush_cache()**: Clear the in-memory URL/IP cache. Returns `{ cleared: bool }`.
- **health_check()**: Perform a health check of the database and scheduler. Returns `{ db_ok: bool, scheduler_alive: bool, last_update: timestamp }`.
- **add_entry(url: str, ip?: str, date?: str, score?: float, source?: str)**: Manually add a blacklist entry. Returns `{ success: bool }`.
- **remove_entry(value: str)**: Remove a blacklist entry by URL or IP address. Returns `{ success: bool }`.

## Configuration

The client can be configured via `config.json`:

- `blacklist_sources`: URLs for blacklist feeds
- `update_time`: Daily update schedule (default: "00:00")
- `cache_size`: In-memory cache size (default: 10000)
- `log_level`: Logging verbosity (default: "INFO")

## Development

Clone the repository and install in development mode:

```bash
git clone <repository-url>
cd sec-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## License

MIT

## About Montimage

sec-mcp is developed and maintained by [Montimage](https://www.montimage.eu), a company specializing in cybersecurity and network monitoring solutions. Montimage provides innovative security tools and services to help organizations protect their digital assets and ensure the security of their networks.

For questions or support, please contact us at contact@montimage.eu.
