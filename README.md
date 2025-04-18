# MCP Server for security checking (url, domain, ip address)

A Python library and CLI tool for checking domains, URLs, or IP addresses against a blacklist for phishing and malware threats. Integrated with an always-running MCP server for AI-driven workflows.

## Features

- Check domains, URLs, and IPs against multiple blacklist sources
- Automated daily updates from OpenPhish, PhishStats, and URLhaus
- High-throughput performance with SQLite backend and in-memory caching
- CLI interface for manual checks and batch processing
- MCP server integration for AI-driven workflows

## Installation

```bash
pip install sec-mcp
```

## Usage

### CLI Usage

Check a single URL:
```bash
sec-mcp check https://example.com
```

Check multiple URLs from a file:
```bash
sec-mcp batch urls.txt
```

View blacklist status:
```bash
sec-mcp status
```

Update the blacklist database manually:
```bash
sec-mcp update
```

If `sec-mcp update` is not found, reinstall or run via module:
```bash
pip install -e .
sec-mcp update
# or
python3 -m sec_mcp.interface update
```

### MCP Server Usage

**Ensure package is installed locally (e.g., development mode):**
```bash
pip install -e .
```

Start the MCP server in persistent mode:
```bash
python3 start_server.py
```

**Server Logs**

- A log file `mcp-server.log` is created in the project root (same folder as `start_server.py`).
- All server activity and errors are recorded here using the configured log level (default: INFO).
- To follow logs live:
```bash
tail -f mcp-server.log
```

### Quick STDIO Test

Test the MCP server directly over STDIO without an external client.
Suppress the startup banner (stderr) to get only the JSON response:
```bash
printf '{"tool":"check_blacklist","input":{"value":"https://example.com"}}\n' \
  | python3 start_server.py 2>/dev/null
```

You should see the JSON response on stdout:
```json
{"is_safe": true, "explain": "Not blacklisted"}
```

### Python Library Usage

```python
from sec_mcp import Core

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

## Configuring sec-mcp with Claude (MCP Client)

To use your MCP Server for security checking (sec-mcp) with an MCP client such as Claude, add it to your Claude configuration as follows:

```json
{
  "mcpServers": {
    "sec-mcp": {
      "command": ".venv/bin/python3",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}
```

- Ensure you have installed all dependencies in your virtual environment (`.venv`).
- The `command` should point to your Python executable inside `.venv` for best isolation.
- The `args` array should launch your MCP server using the provided script.
- You can add other MCP servers in the same configuration if needed.

This setup allows Claude (or any compatible MCP client) to connect to your sec-mcp server and use its `check_blacklist` tool for real-time security checks on URLs, domains, or IP addresses.

For more details and advanced configuration, see the [Model Context Protocol examples](https://modelcontextprotocol.io/examples).

## Development

Clone the repository and install in development mode:

```bash
git clone <repository-url>
cd sec-mcp
pip install -e .
```

## License

MIT
