# sec-mcp: Security Checking Toolkit

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
- **Smart Optimizations**: Tiered lookup, URL normalization, and integer IPv4 storage for maximum efficiency
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

- Python 3.8+
- SQLite 3
- Optional: `pytricia` and `psutil` for benchmarking

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
```

#### Batch Check
```bash
# From a file (one URL/domain/IP per line)
sec-mcp batch urls.txt

# With output to file
sec-mcp batch urls.txt --output results.json
```

#### Status and Updates
```bash
# Check blacklist status
sec-mcp status

# Update blacklists
sec-mcp update

# Get detailed statistics
sec-mcp stats
```

### Python API

```python
from sec_mcp import SecMCP

# Initialize client
client = SecMCP()

# Update database (run once after installation)
client.update()

# Single check
result = client.check("https://example.com")
print(f"Safe: {result.is_safe}")
print(f"Source: {result.source}")

# Batch check
urls = ["https://example.com", "https://test.com", "192.168.1.1"]
results = client.check_batch(urls)
for r in results:
    print(f"{r.value}: {'SAFE' if r.is_safe else 'BLOCKED'}")

# Get statistics
status = client.get_status()
print(f"Total entries: {status.total_entries}")
print(f"Last update: {status.last_update}")
```

### MCP Server

sec-mcp can run as an MCP server for AI/LLM integration (e.g., Claude, Windsurf, Cursor).

#### Setup

1. **Install sec-mcp** in a virtual environment (see Quick Start)

2. **Update the blacklist**:
   ```bash
   sec-mcp update
   ```

3. **Configure your MCP client** (e.g., `claude_desktop_config.json`):
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

   > **Important**: Use the absolute path to your virtual environment's Python executable.
   > - macOS/Linux: `/path/to/.venv/bin/python`
   > - Windows: `C:\path\to\.venv\Scripts\python.exe`

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

1. **Tiered Lookup (Hot/Cold Sources)**:
   - Checks frequently-hit sources first for early exit
   - 70-90% of lookups hit hot sources
   - Based on production data analysis

2. **URL Normalization**:
   - Automatically catches variations: `HTTP://EVIL.COM/` → `http://evil.com`
   - Removes tracking parameters: `?utm_source=spam`, `?fbclid=123`
   - 15-25% memory reduction

3. **Integer IPv4 Storage**:
   - 4 bytes per IP (vs 13+ bytes as string)
   - 5-10% faster comparisons
   - ~1-2MB memory savings

### Monitoring Performance

```python
# Via MCP tool or Python API
metrics = client.get_storage_metrics()

# Returns:
{
  "total_lookups": 1234,
  "domain_lookups": 567,
  "url_lookups": 432,
  "ip_lookups": 235,
  "avg_lookup_time_ms": "0.0123",
  "memory_usage_mb": "45.3",
  "hit_rate": 0.89,
  "using_pytricia": true
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
# Install dependencies
pip install pytricia psutil

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

### Default Database Locations

- **macOS**: `~/Library/Application Support/sec-mcp/mcp.db`
- **Linux**: `~/.local/share/sec-mcp/mcp.db`
- **Windows**: `%APPDATA%\sec-mcp\mcp.db`

### Custom Database Path

```bash
export MCP_DB_PATH=/path/to/custom/location/mcp.db
```

### Configuration File

Edit `config.json` to customize:

```json
{
  "blacklist_sources": {
    "PhishTank": "https://...",
    "URLhaus": "https://..."
  },
  "update_time": "00:00",
  "cache_size": 10000,
  "log_level": "INFO"
}
```

---

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/montimage/sec-mcp.git
cd sec-mcp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install pytricia psutil pytest
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sec_mcp --cov-report=html
```

### Project Structure

```
sec-mcp/
├── sec_mcp/              # Main package
│   ├── __init__.py
│   ├── storage.py        # v1 storage (database-only)
│   ├── storage_v2.py     # v2 storage (hybrid in-memory)
│   ├── start_server.py   # MCP server
│   └── cli.py           # CLI interface
├── benchmark.py          # Benchmark script
├── run_benchmark.sh      # Benchmark helper script
├── dev-docs/            # Development documentation (git-ignored)
├── tests/               # Test suite
└── README.md            # This file
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

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## Acknowledgments

- Threat intelligence sources: OpenPhish, PhishTank, PhishStats, URLhaus, BlocklistDE, CINSSCORE, and others
- Built with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- Powered by Python and SQLite
