"""Test the core functionality of the MCP client."""
import pytest
from sec_mcp.core import Core, CheckResult
from sec_mcp.storage import Storage
from datetime import datetime

@pytest.fixture
def core():
    return Core()

def test_check_result():
    """Test CheckResult creation and json conversion"""
    result = CheckResult(blacklisted=True, explanation="Test blacklist")
    json_result = result.to_json()
    assert json_result["is_safe"] is False
    assert json_result["explain"] == "Test blacklist"

@pytest.mark.asyncio
async def test_check_safe_url(core):
    """Test checking a known safe URL"""
    result = core.check("https://example.com")
    assert not result.blacklisted
    assert "Not blacklisted" in result.explanation

@pytest.mark.asyncio
async def test_check_blacklisted_url(core):
    """Test checking a blacklisted URL"""
    # Add a test URL to the blacklist
    core.storage.add_entries([("https://malicious-test.com", "TestSource")])
    result = core.check("https://malicious-test.com")
    assert result.blacklisted
    assert "TestSource" in result.explanation

def test_batch_check(core):
    """Test checking multiple URLs in batch"""
    urls = ["https://example1.com", "https://example2.com"]
    results = core.check_batch(urls)
    assert len(results) == 2
    assert all(isinstance(r, CheckResult) for r in results)

def test_status_info(core):
    """Test getting status information"""
    status = core.get_status()
    assert isinstance(status.entry_count, int)
    assert isinstance(status.last_update, datetime)
    assert isinstance(status.sources, list)
    assert status.server_status == "Running (STDIO)"
