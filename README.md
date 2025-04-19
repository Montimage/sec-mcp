# sec-mcp: Security Checking Toolkit

A Python toolkit providing security checks for domains, URLs, IPs, and more. Integrate easily into any Python application, use via terminal CLI, or run as an MCP server to enrich LLM context with real-time threat insights.

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
| `flush_cache`         | `flush_cache()`                 | Clear the in-memory URL/IP cache.                                                     |
| `add_entry`           | `add_entry(url, ip, ...)`       | Manually add a blacklist entry.                                                       |
| `remove_entry`        | `remove_entry(value: str)`      | Remove a blacklist entry by URL or IP address.                                        |
| `update_blacklists`   | `update_blacklists()`           | Force immediate update of all blacklists.                                             |
| `health_check`        | `health_check()`                | Perform a health check of the database and scheduler.                                 |

### MCP Server Usage

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
         "command": "/[ABSOLUTE_PATH_TO_VENV]/.venv/bin/python3",
         "args": ["-m", "sec_mcp.start_server"]
       }
     }
   }
   ```
   > **Note:**
   > - Use `python3` (or `python`) if installed system-wide via pip.
   > - Ensure you have installed all dependencies in your virtual environment (`.venv`).
   > - The `command` should point to your Python executable inside `.venv` for best isolation.
   > - The `args` array should launch your MCP server using the provided script.
   > - You can add other MCP servers in the same configuration if needed.

This setup allows Claude (or any compatible MCP client) to connect to your sec-mcp server and use its `check_blacklist` tool for real-time security checks on URLs, domains, or IP addresses.

For more details and advanced configuration, see the [Model Context Protocol examples](https://modelcontextprotocol.io/examples).

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
         "command": "/[ABSOLUTE_PATH_TO_VENV]/.venv/bin/python3",
         "args": ["-m", "sec_mcp.start_server"]
       }
     }
   }
   ```
   > **Note:**
   > - Ensure all dependencies are installed in your virtual environment (`.venv`).
   > - This is the recommended configuration for integration with AI-driven clients.

Clients will then use the built-in `check_blacklist` tool over JSON/STDIO for real-time security checks.

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
