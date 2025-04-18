#!/usr/bin/env python3
"""Start the MCP server in persistent mode."""

from sec_mcp.mcp_server import mcp
import sys
from sec_mcp.utility import setup_logging

def main():
    """Entrypoint for MCP server via console script."""
    setup_logging()
    print("Starting MCP server with STDIO transport...", file=sys.stderr)
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
