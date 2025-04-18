# sec-mcp: Security Checking Toolkit

A Python toolkit providing security checks for domains, URLs, IPs, and more. Integrate easily into any Python application, use via terminal CLI, or run as an MCP server to enrich LLM context with real-time threat insights.

## Features

- Comprehensive security checks for domains, URLs, IP addresses, and more against multiple blacklist feeds
- On-demand updates from OpenPhish, PhishStats, URLhaus and custom sources
- High-performance, thread-safe SQLite storage with in-memory caching for fast lookups
- Python API via `SecMCP` class for easy integration into your applications
- Intuitive Click-based CLI for interactive single or batch scans
- Built-in MCP server support for LLM/AI integrations over JSON/STDIO

## Installation

```bash
pip install sec-mcp
```

## Usage via CLI

1. Install the package:
   ```bash
   pip install sec-mcp
   ```
2. Check a single URL/domain/IP:
   ```bash
   sec-mcp check https://example.com
   ```
3. Batch check from a file:
   ```bash
   sec-mcp batch urls.txt
   ```
4. View blacklist status:
   ```bash
   sec-mcp status
   ```
5. Manually trigger an update:
   ```bash
   sec-mcp update
   ```

## Usage via API (Python)

1. Install in your project:
   ```bash
   pip install sec-mcp
   ```
2. Import and initialize:
   ```python
   from sec_mcp import SecMCP

   client = SecMCP()
   ```
3. Single check:
   ```python
   result = client.check("https://example.com")
   print(result.to_json())
   ```
4. Batch check:
   ```python
   urls = ["https://example.com", "https://test.com"]
   results = client.check_batch(urls)
   for r in results:
       print(r.to_json())
   ```
5. Get status and update:
   ```python
   status = client.get_status()
   print(status.to_json())

   client.update()
   ```

## Usage via MCP Client

To run sec-mcp as an MCP server for AI-driven clients (e.g., Claude):

1. Install in editable mode (for development):
   ```bash
   pip install -e .
   ```
2. Start the MCP server:
   ```bash
   sec-mcp-server
   ```
3. Configure your MCP client (e.g., Claude, Windsurf, Cursor) to point at the command:
   ```json
   {
     "mcpServers": {
       "sec-mcp": {
         "command": "uv",
         "args": ["--directory","/Users/montimage/workspace/montimage/sec-mcp","run", "-m", "sec_mcp.start_server"]
       }
     }
   }
   ```
   > **Note:**
   > - The `--directory` argument ensures the working directory is set to your project root, so Python treats `sec_mcp` as a package and all relative imports work correctly. This is essential for correct module resolution when running as a module (`-m`).
   > - Update the path in `--directory` if your project is in a different location.
   > - Ensure all dependencies are installed in your virtual environment (`.venv`).
   > - This is the recommended configuration for integration with AI-driven clients.

Clients will then use the built-in `check_blacklist` tool over JSON/STDIO for real-time security checks.

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
      "command": "/[ABSOLUTE_PATH_TO_VENV]/.venv/bin/python3",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}
```

> **Note:** If you installed `sec-mcp` in a virtual environment, set the `command` path to your `.venv` Python as shown above. If you installed it globally or via `pip` (system-wide), use your system Python executable (e.g., `python3` or the full path to your Python):

```json
{
  "mcpServers": {
    "sec-mcp": {
      "command": "python3",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}
```

> **Tip:**
> - Use the absolute path to the Python executable for virtual environments for isolation.
> - Use `python3` (or `python`) if installed system-wide via pip.

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
