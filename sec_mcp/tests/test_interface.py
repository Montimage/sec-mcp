"""Test the MCP server interface."""
import pytest
from sec_mcp.interface import MCPServer
from sec_mcp.core import Core

@pytest.fixture
def mcp_server():
    core = Core()
    return MCPServer(core)

@pytest.mark.asyncio
async def test_check_blacklist_safe_url(mcp_server):
    """Test checking a safe URL through the MCP interface."""
    result = await mcp_server.check_blacklist("https://example.com")
    assert result["is_safe"] is True
    assert "Not blacklisted" in result["explain"]

@pytest.mark.asyncio
async def test_check_blacklist_malicious_url(mcp_server):
    """Test checking a blacklisted URL through the MCP interface."""
    # Add a test URL to the blacklist
    mcp_server.core.storage.add_entries([
        ("https://malicious.test", "TestBlacklist")
    ])
    result = await mcp_server.check_blacklist("https://malicious.test")
    assert result["is_safe"] is False
    assert "TestBlacklist" in result["explain"]

@pytest.mark.asyncio
async def test_check_blacklist_invalid_input(mcp_server):
    """Test checking an invalid URL through the MCP interface."""
    result = await mcp_server.check_blacklist("not-a-valid-url")
    assert result["is_safe"] is False
    assert "Invalid input format" in result["explain"]
