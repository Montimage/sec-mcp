#!/usr/bin/env python3
"""Start the MCP server in persistent mode."""

import sys
import os

# Adjust sys.path to allow direct execution of this script
# This script is in /Users/montimage/workspace/montimage/sec-mcp/sec_mcp/
# The project root is /Users/montimage/workspace/montimage/sec-mcp/
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from sec_mcp.mcp_server import mcp
from sec_mcp.utility import setup_logging

def main():
    """Entrypoint for MCP server via console script."""
    setup_logging()
    print("Starting MCP server with STDIO transport...", file=sys.stderr)
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
