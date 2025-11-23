#!/usr/bin/env python3
"""Start the MCP server in persistent mode."""

import json
import os
import sys

# Adjust sys.path to allow direct execution of this script
# This script is in /Users/montimage/workspace/montimage/sec-mcp/sec_mcp/
# The project root is /Users/montimage/workspace/montimage/sec-mcp/
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import click
from mcp.server.fastmcp import FastMCP

from sec_mcp.utility import setup_logging


def print_stdio_config():
    """Print copy-paste ready configuration for STDIO mode."""
    python_path = sys.executable
    use_v2 = os.getenv("MCP_USE_V2_STORAGE", "false").lower() in ("true", "1", "yes")

    config = {
        "mcpServers": {
            "sec-mcp": {
                "command": python_path,
                "args": ["-m", "sec_mcp.start_server"],
                "env": {"MCP_USE_V2_STORAGE": "true" if use_v2 else "false"},
            }
        }
    }

    print("\n" + "=" * 80, file=sys.stderr)
    print("✓ MCP Server started successfully (STDIO mode)", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print("\n📋 Copy-paste this into your MCP client configuration:\n", file=sys.stderr)
    print(json.dumps(config, indent=2), file=sys.stderr)
    print("\n" + "=" * 80 + "\n", file=sys.stderr)


def print_http_config(host: str, port: int):
    """Print copy-paste ready configuration for HTTP mode."""
    url = f"http://{host}:{port}/sse"

    config = {"mcpServers": {"sec-mcp": {"url": url, "transport": "sse"}}}

    print("\n" + "=" * 80, file=sys.stderr)
    print("✓ MCP Server started successfully (HTTP mode)", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"\n🌐 Server running at: http://{host}:{port}", file=sys.stderr)
    print(f"📡 SSE endpoint: {url}", file=sys.stderr)
    print("\n📋 Copy-paste this into your MCP client configuration:\n", file=sys.stderr)
    print(json.dumps(config, indent=2), file=sys.stderr)
    print("\n" + "=" * 80, file=sys.stderr)
    print("💡 Tip: Press Ctrl+C to stop the server", file=sys.stderr)
    print("=" * 80 + "\n", file=sys.stderr)


@click.command()
@click.option(
    "--transport",
    "-t",
    type=click.Choice(["stdio", "http"], case_sensitive=False),
    default=lambda: os.getenv("MCP_TRANSPORT", "stdio").lower(),
    help="Transport mode: stdio (default) or http",
    show_default=True,
)
@click.option(
    "--host",
    "-h",
    default=lambda: os.getenv("MCP_HOST", "localhost"),
    help="Host address for HTTP server (only used with --transport=http)",
    show_default=True,
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=lambda: int(os.getenv("MCP_PORT", "8000")),
    help="Port for HTTP server (only used with --transport=http)",
    show_default=True,
)
def main(transport: str, host: str, port: int):
    """
    Start the MCP server with configurable transport.

    The server can run in two modes:

    \b
    STDIO mode (default):
      Communicates via standard input/output.
      Best for local CLI tools and desktop applications.

    \b
    HTTP mode:
      Runs an HTTP server with Server-Sent Events (SSE).
      Best for web applications and remote access.

    \b
    Examples:
      # Start with default STDIO transport
      sec-mcp-server

      # Start with HTTP transport on default port 8000
      sec-mcp-server --transport http

      # Start HTTP server on custom host and port
      sec-mcp-server -t http -h 0.0.0.0 -p 3000

      # Use environment variables
      MCP_TRANSPORT=http MCP_PORT=3000 sec-mcp-server
    """
    setup_logging()

    transport = transport.lower()

    if transport == "stdio":
        print_stdio_config()
        # Import and run with default settings
        from sec_mcp.mcp_server import mcp
        mcp.run(transport="stdio")
    elif transport == "http":
        print_http_config(host, port)
        # Create FastMCP with custom host/port settings
        from sec_mcp import mcp_server

        # Reinitialize the global mcp instance with custom settings
        mcp_server.mcp = FastMCP("mcp-blacklist", host=host, port=port)

        # Re-register all tools (decorators will register on the new instance)
        import importlib
        importlib.reload(mcp_server)

        mcp_server.mcp.run(transport="sse")
    else:
        click.echo(f"Error: Invalid transport '{transport}'. Use 'stdio' or 'http'.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
