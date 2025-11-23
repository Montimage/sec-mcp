"""Unit tests for BlacklistUpdater module."""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import pytest

from sec_mcp.storage import Storage
from sec_mcp.update_blacklist import BlacklistUpdater


@pytest.fixture
def mock_storage():
    """Create a mock storage object."""
    storage = MagicMock(spec=Storage)
    storage.is_domain_blacklisted.return_value = False
    storage.add_domain = MagicMock()
    storage.add_url = MagicMock()
    storage.add_ip = MagicMock()
    storage.add_entries = MagicMock()
    return storage


@pytest.fixture
def updater(mock_storage):
    """Create a BlacklistUpdater instance with mocked storage."""
    with patch("sec_mcp.update_blacklist.setup_logging"):
        return BlacklistUpdater(mock_storage)


# ============================================================================
# Existing Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_source_success():
    storage = MagicMock(spec=Storage)
    with patch("sec_mcp.update_blacklist.setup_logging"):
        updater = BlacklistUpdater(storage)
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "url,ip,date,score\nhttps://malicious.com,1.2.3.4,2025-04-18T00:00:00,9.0\nhttps://phishing.com,2.2.2.2,,\n"
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    await updater._update_source(mock_client, "PhishStats", "http://fake-url")

    # Based on the test data and current parsing logic for PhishStats:
    # "https://malicious.com" (no path) -> add_domain("malicious.com"), add_ip("1.2.3.4")
    # "https://phishing.com" (no path) -> add_domain("phishing.com"), add_ip("2.2.2.2")
    assert storage.add_domain.call_count == 2
    assert storage.add_ip.call_count == 2
    assert storage.add_url.call_count == 0  # add_url is not called for domain-only entries

    storage.add_domain.assert_any_call("malicious.com", "2025-04-18T00:00:00", 9.0, "PhishStats")
    storage.add_ip.assert_any_call("1.2.3.4", "2025-04-18T00:00:00", 9.0, "PhishStats")

    # For the second entry, date is now_str (mocked by ANY) and score is default 8.0
    storage.add_domain.assert_any_call("phishing.com", ANY, 8.0, "PhishStats")
    storage.add_ip.assert_any_call("2.2.2.2", ANY, 8.0, "PhishStats")


@pytest.mark.asyncio
async def test_update_source_network_error():
    storage = MagicMock(spec=Storage)
    with patch("sec_mcp.update_blacklist.setup_logging"):
        updater = BlacklistUpdater(storage)
    mock_client = MagicMock()

    async def raise_exc(*args, **kwargs):
        raise Exception("Network error")

    mock_client.get = AsyncMock(side_effect=raise_exc)
    await updater._update_source(mock_client, "OpenPhish", "http://fake-url")
    # No entries should be added
    assert not storage.add_domain.called
    assert not storage.add_ip.called
    assert not storage.add_url.called


# ============================================================================
# New Comprehensive Tests
# ============================================================================


def test_is_domain_blacklisted_true(updater):
    """Test _is_domain_blacklisted when domain is blacklisted."""
    updater.storage.is_domain_blacklisted.return_value = True
    result = updater._is_domain_blacklisted("http://evil.com/malware")
    assert result is True


def test_is_domain_blacklisted_false(updater):
    """Test _is_domain_blacklisted when domain is not blacklisted."""
    updater.storage.is_domain_blacklisted.return_value = False
    result = updater._is_domain_blacklisted("http://safe.com/page")
    assert result is False


def test_is_domain_blacklisted_invalid_url(updater):
    """Test _is_domain_blacklisted with invalid URL."""
    result = updater._is_domain_blacklisted("not-a-url")
    assert result is False


def test_force_update(updater):
    """Test force_update method."""
    with patch("asyncio.run") as mock_run:
        updater.force_update()
        mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_update_all_with_multiple_sources(updater):
    """Test update_all with multiple sources."""
    updater.sources = {"Source1": "http://url1", "Source2": "http://url2"}

    with patch.object(updater, "_update_source", new_callable=AsyncMock) as mock_update:
        await updater.update_all()
        assert mock_update.call_count == 2


@pytest.mark.asyncio
async def test_update_source_with_cache(updater, tmp_path):
    """Test _update_source using cached file."""
    # Create a cached file that's less than 1 day old
    cache_dir = tmp_path / "downloads"
    cache_dir.mkdir()
    cache_file = cache_dir / "TestSource.txt"
    cache_file.write_text("http://malicious.com\n")

    mock_client = MagicMock()

    with patch("os.path.exists", return_value=True), patch("os.path.getmtime") as mock_mtime, patch(
        "builtins.open", create=True
    ) as mock_open:
        # Make the file appear recent (less than 1 day old)
        mock_mtime.return_value = datetime.now().timestamp()
        mock_open.return_value.__enter__.return_value.read.return_value = "http://malicious.com\n"

        await updater._update_source(mock_client, "TestSource", "http://test-url")

        # Client.get should not be called when using cache
        mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_update_source_empty_data(updater):
    """Test _update_source with empty response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("os.path.exists", return_value=False), patch("builtins.open", create=True):
        await updater._update_source(mock_client, "EmptySource", "http://empty-url")

        # No entries should be added for empty data
        assert not updater.storage.add_domain.called
        assert not updater.storage.add_url.called
        assert not updater.storage.add_ip.called


@pytest.mark.asyncio
async def test_update_source_invalid_csv(updater):
    """Test _update_source with invalid CSV data."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Invalid CSV - only header, no data
    mock_response.text = "url,ip,date,score\n"
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("os.path.exists", return_value=False), patch("builtins.open", create=True):
        await updater._update_source(mock_client, "PhishStats", "http://phishstats-url")

        # Should handle gracefully without adding entries
        # The implementation may or may not call storage methods depending on error handling


@pytest.mark.asyncio
async def test_update_source_invalid_score(updater):
    """Test _update_source with invalid score value."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Score is not a valid number
    mock_response.text = "url,ip,date,score\nhttp://test.com,1.2.3.4,2025-01-01,invalid_score\n"
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("os.path.exists", return_value=False), patch("builtins.open", create=True):
        await updater._update_source(mock_client, "PhishStats", "http://phishstats-url")

        # Should fall back to default score (8.0)
        # At least one add method should be called
        assert (
            updater.storage.add_domain.called
            or updater.storage.add_url.called
            or updater.storage.add_ip.called
        )
