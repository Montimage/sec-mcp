from unittest.mock import MagicMock, patch

import pytest

from sec_mcp.sec_mcp import CheckResult, SecMCP, StatusInfo


@pytest.fixture
def secmcp():
    with patch("sec_mcp.sec_mcp.create_storage") as mock_create_storage, patch(
        "sec_mcp.sec_mcp.BlacklistUpdater"
    ) as mock_updater:
        # Create mock storage instance
        mock_storage = MagicMock()
        mock_create_storage.return_value = mock_storage

        # Create mock updater instance
        mock_updater_instance = MagicMock()
        mock_updater.return_value = mock_updater_instance

        # Create SecMCP instance with mocks
        instance = SecMCP()

        yield instance


def test_check_blacklisted_and_safe(secmcp):
    # Mock storage behavior for domain checks
    secmcp.storage.is_domain_blacklisted.side_effect = lambda domain: domain == "bad.com"
    secmcp.storage.get_domain_blacklist_source.return_value = "TestSource"

    result = secmcp.check("bad.com")
    assert isinstance(result, CheckResult)
    assert result.blacklisted is True
    assert "TestSource" in result.explanation

    result2 = secmcp.check("good.com")
    assert isinstance(result2, CheckResult)
    assert result2.blacklisted is False
    assert "Not blacklisted" in result2.explanation


def test_check_batch(secmcp):
    # Mock storage behavior for domain checks
    secmcp.storage.is_domain_blacklisted.side_effect = lambda domain: domain == "bad.com"
    # get_domain_blacklist_source will be called for 'bad.com'
    secmcp.storage.get_domain_blacklist_source.return_value = "BatchSource"
    results = secmcp.check_batch(["bad.com", "good.com"])
    assert len(results) == 2
    assert results[0].blacklisted is True
    assert results[1].blacklisted is False


def test_get_status(secmcp):
    secmcp.storage.count_entries.return_value = 42
    secmcp.storage.get_last_update.return_value = pytest.approx(
        1713465600, rel=1e-3
    )  # mock timestamp
    secmcp.storage.get_active_sources.return_value = ["S1", "S2"]
    status = secmcp.get_status()
    assert isinstance(status, StatusInfo)
    assert status.entry_count == 42
    assert isinstance(status.sources, list)
    assert status.server_status == "Running (STDIO)"


def test_update_calls_updater(secmcp):
    secmcp.updater.force_update = MagicMock()
    secmcp.update()
    secmcp.updater.force_update.assert_called_once()


def test_sample_entries(secmcp):
    secmcp.storage.sample_entries.return_value = ["a", "b"]
    sample = secmcp.sample(2)
    assert sample == ["a", "b"]


# ============================================================================
# Additional tests for missing coverage
# ============================================================================


def test_check_ip_blacklisted(secmcp):
    """Test check method with blacklisted IP."""
    secmcp.storage.is_ip_blacklisted.return_value = True
    secmcp.storage.get_ip_blacklist_source.return_value = "IPSource"
    result = secmcp.check("192.168.1.100")
    assert result.blacklisted is True
    assert "IPSource" in result.explanation


def test_check_url_blacklisted(secmcp):
    """Test check method with blacklisted URL."""
    secmcp.storage.is_url_blacklisted.return_value = True
    secmcp.storage.get_url_blacklist_source.return_value = "URLSource"
    result = secmcp.check("http://evil.com/malware")
    assert result.blacklisted is True
    assert "URLSource" in result.explanation


def test_check_url_with_blacklisted_domain(secmcp):
    """Test check method with URL from blacklisted domain."""
    secmcp.storage.is_url_blacklisted.return_value = False
    secmcp.storage.is_domain_blacklisted.return_value = True
    secmcp.storage.get_domain_blacklist_source.return_value = "DomainSource"
    result = secmcp.check("http://evil.com/page")
    assert result.blacklisted is True
    assert "DomainSource" in result.explanation


def test_check_invalid_input(secmcp):
    """Test check method with invalid input."""
    result = secmcp.check("not-a-valid-anything")
    assert result.blacklisted is False
    assert "Invalid input type" in result.explanation


def test_check_domain_blacklisted(secmcp):
    """Test check_domain method with blacklisted domain."""
    secmcp.storage.is_domain_blacklisted.return_value = True
    secmcp.storage.get_domain_blacklist_source.return_value = "DomainSource"
    result = secmcp.check_domain("evil.com")
    assert result.blacklisted is True
    assert "DomainSource" in result.explanation


def test_check_url_blacklisted_via_method(secmcp):
    """Test check_url method with blacklisted URL."""
    secmcp.storage.is_url_blacklisted.return_value = True
    secmcp.storage.get_url_blacklist_source.return_value = "URLSource"
    result = secmcp.check_url("http://phishing.com/login")
    assert result.blacklisted is True
    assert "URLSource" in result.explanation


def test_check_url_with_domain_blacklisted_via_method(secmcp):
    """Test check_url method with URL from blacklisted domain."""
    secmcp.storage.is_url_blacklisted.return_value = False
    secmcp.storage.is_domain_blacklisted.return_value = True
    secmcp.storage.get_domain_blacklist_source.return_value = "DomainSource"
    result = secmcp.check_url("http://evil.com/page")
    assert result.blacklisted is True
    assert "DomainSource" in result.explanation


def test_check_ip_blacklisted_via_method(secmcp):
    """Test check_ip method with blacklisted IP."""
    secmcp.storage.is_ip_blacklisted.return_value = True
    secmcp.storage.get_ip_blacklist_source.return_value = "IPSource"
    result = secmcp.check_ip("192.168.1.100")
    assert result.blacklisted is True
    assert "IPSource" in result.explanation


# ============================================================================
# Tests for helper methods
# ============================================================================


def test_is_url():
    """Test is_url static method."""
    assert SecMCP.is_url("http://example.com") is True
    assert SecMCP.is_url("https://example.com") is True
    assert SecMCP.is_url("HTTP://example.com") is True
    assert SecMCP.is_url("example.com") is False
    assert SecMCP.is_url("192.168.1.1") is False


def test_is_ip():
    """Test is_ip static method."""
    assert SecMCP.is_ip("192.168.1.1") is True
    assert SecMCP.is_ip("2001:db8::1") is True
    assert SecMCP.is_ip("example.com") is False
    assert SecMCP.is_ip("not-an-ip") is False
    assert SecMCP.is_ip("999.999.999.999") is False


def test_is_domain():
    """Test is_domain static method."""
    assert SecMCP.is_domain("example.com") is True
    assert SecMCP.is_domain("sub.example.com") is True
    assert SecMCP.is_domain("http://example.com") is False
    assert SecMCP.is_domain("192.168.1.1") is False
    assert SecMCP.is_domain("example") is False
    assert SecMCP.is_domain("example.com.") is False


def test_extract_domain():
    """Test extract_domain static method."""
    assert SecMCP.extract_domain("http://example.com/path") == "example.com"
    assert SecMCP.extract_domain("https://example.com:8080/path") == "example.com"
    assert SecMCP.extract_domain("http://sub.example.com/path?query=1") == "sub.example.com"
    # Fragment is not handled by the current implementation
    assert SecMCP.extract_domain("http://example.com/path") == "example.com"
    assert SecMCP.extract_domain("http://localhost") is None


# ============================================================================
# Tests for dataclasses
# ============================================================================


def test_check_result_to_json():
    """Test CheckResult.to_json method."""
    result = CheckResult(blacklisted=True, explanation="Test")
    json_data = result.to_json()
    assert json_data["is_safe"] is False
    assert json_data["explain"] == "Test"

    result2 = CheckResult(blacklisted=False, explanation="Safe")
    json_data2 = result2.to_json()
    assert json_data2["is_safe"] is True


def test_status_info_to_json():
    """Test StatusInfo.to_json method."""
    from datetime import datetime

    status = StatusInfo(
        entry_count=100,
        last_update=datetime(2025, 1, 1, 12, 0, 0),
        sources=["Source1", "Source2"],
        server_status="Running",
    )
    json_data = status.to_json()
    assert json_data["entry_count"] == 100
    assert json_data["last_update"] == "2025-01-01T12:00:00"
    assert json_data["sources"] == ["Source1", "Source2"]
    assert json_data["server_status"] == "Running"
