# Model Context Protocol (MCP) Client

A Python library and CLI tool for checking domains, URLs, or IP addresses against a blacklist for phishing and malware threats. Integrated with an always-running MCP server for AI-driven workflows.

## Features

- Check domains, URLs, and IPs against multiple blacklist sources
- Automated daily updates from OpenPhish, PhishStats, and URLhaus
- High-throughput performance with SQLite backend and in-memory caching
- CLI interface for manual checks and batch processing
- MCP server integration for AI-driven workflows

## Installation

```bash
pip install mcp-client
```

## Usage

### CLI Usage

Check a single URL:
```bash
mcp check https://example.com
```

Check multiple URLs from a file:
```bash
mcp batch urls.txt
```

View blacklist status:
```bash
mcp status
```

### MCP Server Usage

The MCP server can be started in persistent mode:

```bash
./start_server.py
```

This starts an MCP server with STDIO transport that exposes the following tool:

- `check_blacklist`: Check if a domain, URL, or IP is in the blacklist
  - Input: `value` (string) - The domain, URL, or IP to check
  - Output: JSON with `is_safe` (boolean) and `explain` (string)

### Python Library Usage

```python
from mcp_client import Core

# Initialize the client
core = Core()

# Check a single URL
result = core.check("https://example.com")
print(f"Safe: {not result.blacklisted}")
print(f"Explanation: {result.explanation}")

# Check multiple URLs
urls = ["https://example.com", "https://test.com"]
results = core.check_batch(urls)
```

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
cd mcp-client
pip install -e .
```

## License

MIT
