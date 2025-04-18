"""Test script for the MCP server functionality."""
import asyncio
from mcp_client.interface import MCPServer
from mcp_client.core import Core

async def test_server():
    core = Core()
    server = MCPServer(core)
    
    # Test the check_blacklist tool
    result = await server.check_blacklist("https://example.com")
    print("Check result:", result)

if __name__ == "__main__":
    asyncio.run(test_server())
