#!/usr/bin/env python3
"""Start the MCP server in persistent mode."""

from mcp_client.interface import mcp, MCPServer
from mcp_client.core import Core
from mcp_client.utility import setup_logging

if __name__ == "__main__":
    # Set up logging
    setup_logging()
    
    # Initialize core and server
    core = Core()
    server = MCPServer(core)
    
    # Start the server with STDIO transport
    print("Starting MCP server with STDIO transport...")
    mcp.run(transport='stdio')
