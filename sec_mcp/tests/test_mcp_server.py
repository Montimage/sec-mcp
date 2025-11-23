"""
Tests for MCP server tools.

This module tests all MCP server tools including:
- check_batch
- get_status
- update_blacklists
- get_diagnostics
- add_entry
- remove_entry
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from sec_mcp.mcp_server import (
    add_entry,
    check_batch,
    core,
    get_diagnostics,
    get_status,
    remove_entry,
    update_blacklists,
)


class TestCheckBatch:
    """Tests for the check_batch tool."""

    @pytest.mark.asyncio
    async def test_check_batch_all_safe(self):
        """Test check_batch with all safe values."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            # Mock the check method to return safe results
            mock_result = Mock()
            mock_result.blacklisted = False
            mock_result.explanation = "Not blacklisted"
            mock_core.check.return_value = mock_result

            results = await check_batch(["example.com", "google.com"])

            assert len(results) == 2
            assert all(r["is_safe"] for r in results)
            assert results[0]["value"] == "example.com"
            assert results[1]["value"] == "google.com"
            assert mock_core.check.call_count == 2

    @pytest.mark.asyncio
    async def test_check_batch_with_blacklisted(self):
        """Test check_batch with one blacklisted value."""
        with patch("sec_mcp.mcp_server.core") as mock_core:

            def mock_check(value):
                result = Mock()
                if value == "malicious.com":
                    result.blacklisted = True
                    result.explanation = "Blacklisted by OpenPhish"
                else:
                    result.blacklisted = False
                    result.explanation = "Not blacklisted"
                return result

            mock_core.check.side_effect = mock_check

            results = await check_batch(["example.com", "malicious.com"])

            assert len(results) == 2
            assert results[0]["is_safe"] is True
            assert results[1]["is_safe"] is False
            assert "OpenPhish" in results[1]["explanation"]

    @pytest.mark.asyncio
    async def test_check_batch_with_invalid_input(self):
        """Test check_batch with invalid input."""
        with patch("sec_mcp.mcp_server.validate_input") as mock_validate:
            mock_validate.return_value = False

            results = await check_batch(["invalid!!!domain"])

            assert len(results) == 1
            assert results[0]["is_safe"] is False
            assert "Invalid input format" in results[0]["explanation"]

    @pytest.mark.asyncio
    async def test_check_batch_empty_list(self):
        """Test check_batch with empty list."""
        results = await check_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_check_batch_mixed_types(self):
        """Test check_batch with mixed domain/URL/IP."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_result = Mock()
            mock_result.blacklisted = False
            mock_result.explanation = "Not blacklisted"
            mock_core.check.return_value = mock_result

            results = await check_batch(["example.com", "https://test.com/path", "192.168.1.1"])

            assert len(results) == 3
            assert all(isinstance(r, dict) for r in results)
            assert all("is_safe" in r for r in results)


class TestGetStatus:
    """Tests for the get_status tool."""

    @pytest.mark.asyncio
    async def test_get_status_returns_complete_info(self):
        """Test that get_status returns all required fields."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            # Mock status
            mock_status = Mock()
            mock_status.entry_count = 10000
            mock_status.last_update = "2025-01-01 12:00:00"
            mock_status.sources = ["OpenPhish", "URLhaus"]
            mock_status.server_status = "Running"
            mock_core.get_status.return_value = mock_status

            # Mock source counts
            mock_core.storage.get_source_counts.return_value = {"OpenPhish": 5000, "URLhaus": 5000}

            result = await get_status()

            assert result["entry_count"] == 10000
            assert result["last_update"] == "2025-01-01 12:00:00"
            assert "OpenPhish" in result["sources"]
            assert result["server_status"] == "Running"
            assert result["source_counts"]["OpenPhish"] == 5000

    @pytest.mark.asyncio
    async def test_get_status_with_no_entries(self):
        """Test get_status when database is empty."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_status = Mock()
            mock_status.entry_count = 0
            mock_status.last_update = "Never"
            mock_status.sources = []
            mock_status.server_status = "Running"
            mock_core.get_status.return_value = mock_status
            mock_core.storage.get_source_counts.return_value = {}

            result = await get_status()

            assert result["entry_count"] == 0
            assert result["sources"] == []
            assert result["source_counts"] == {}


class TestUpdateBlacklists:
    """Tests for the update_blacklists tool."""

    @pytest.mark.asyncio
    async def test_update_blacklists_success(self):
        """Test successful blacklist update."""
        with patch("sec_mcp.mcp_server.anyio.to_thread.run_sync") as mock_run_sync:
            mock_run_sync.return_value = None

            result = await update_blacklists()

            assert result["updated"] is True
            mock_run_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_blacklists_calls_core_update(self):
        """Test that update_blacklists calls core.update."""
        with patch("sec_mcp.mcp_server.anyio.to_thread.run_sync") as mock_run_sync:
            await update_blacklists()
            # Verify that core.update was passed to run_sync
            args = mock_run_sync.call_args
            assert callable(args[0][0])  # First argument should be core.update


class TestGetDiagnostics:
    """Tests for the get_diagnostics tool."""

    @pytest.mark.asyncio
    async def test_get_diagnostics_summary_mode(self):
        """Test get_diagnostics in summary mode."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.count_entries.return_value = 1000
            mock_core.storage.get_source_counts.return_value = {"OpenPhish": 1000}
            mock_core.storage.get_last_update_per_source.return_value = {"OpenPhish": "2025-01-01"}

            result = await get_diagnostics(mode="summary")

            assert result["mode"] == "summary"
            assert result["total_entries"] == 1000
            assert "OpenPhish" in result["per_source"]

    @pytest.mark.asyncio
    async def test_get_diagnostics_health_mode(self):
        """Test get_diagnostics in health mode."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_status = Mock()
            mock_status.last_update = "2025-01-01 12:00:00"
            mock_core.get_status.return_value = mock_status
            mock_core.storage.count_entries.return_value = 1000

            result = await get_diagnostics(mode="health")

            assert result["mode"] == "health"
            assert result["db_ok"] is True
            assert result["scheduler_alive"] is True
            assert "last_update" in result

    @pytest.mark.asyncio
    async def test_get_diagnostics_health_mode_db_error(self):
        """Test get_diagnostics health mode when DB fails."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.count_entries.side_effect = Exception("DB Error")
            mock_status = Mock()
            mock_status.last_update = "2025-01-01 12:00:00"
            mock_core.get_status.return_value = mock_status

            result = await get_diagnostics(mode="health")

            assert result["db_ok"] is False

    @pytest.mark.asyncio
    async def test_get_diagnostics_performance_mode_v2(self):
        """Test get_diagnostics performance mode with v2 storage."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.get_metrics.return_value = {
                "total_lookups": 5000,
                "cache_hit_rate": 0.85,
            }

            result = await get_diagnostics(mode="performance")

            assert result["mode"] == "performance"
            assert result["total_lookups"] == 5000
            assert result["cache_hit_rate"] == 0.85

    @pytest.mark.asyncio
    async def test_get_diagnostics_performance_mode_v1(self):
        """Test get_diagnostics performance mode with v1 storage (no metrics)."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            # Simulate v1 storage without get_metrics
            delattr(mock_core.storage, "get_metrics") if hasattr(
                mock_core.storage, "get_metrics"
            ) else None
            mock_core.storage = Mock(spec=[])  # Mock without get_metrics

            result = await get_diagnostics(mode="performance")

            assert result["mode"] == "performance"
            assert "error" in result
            # Just check that it mentions metrics are not available
            assert "available" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_get_diagnostics_sample_mode(self):
        """Test get_diagnostics sample mode."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.sample.return_value = [
                {"url": "http://malicious.com", "source": "OpenPhish"},
                {"url": "http://phish.com", "source": "PhishStats"},
            ]

            result = await get_diagnostics(mode="sample", sample_count=2)

            assert result["mode"] == "sample"
            assert result["count"] == 2
            assert len(result["entries"]) == 2
            mock_core.sample.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_get_diagnostics_full_mode(self):
        """Test get_diagnostics full mode."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.count_entries.return_value = 1000
            mock_core.storage.get_source_counts.return_value = {"OpenPhish": 1000}
            mock_core.storage.get_last_update_per_source.return_value = {"OpenPhish": "2025-01-01"}
            mock_core.storage.get_source_type_counts.return_value = {
                "OpenPhish": {"domains": 500, "urls": 500}
            }
            mock_core.storage.get_metrics.return_value = {"total_lookups": 5000}

            result = await get_diagnostics(mode="full")

            assert result["mode"] == "full"
            assert result["total_entries"] == 1000
            assert "per_source" in result
            assert "health" in result
            assert "performance" in result

    @pytest.mark.asyncio
    async def test_get_diagnostics_default_mode(self):
        """Test get_diagnostics with default (summary) mode."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.count_entries.return_value = 1000
            mock_core.storage.get_source_counts.return_value = {}
            mock_core.storage.get_last_update_per_source.return_value = {}

            # Call without mode parameter
            result = await get_diagnostics()

            assert result["mode"] == "summary"


class TestAddEntry:
    """Tests for the add_entry tool."""

    @pytest.mark.asyncio
    async def test_add_entry_with_all_params(self):
        """Test add_entry with all parameters."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            result = await add_entry(
                url="http://malicious.com",
                ip="192.168.1.1",
                date="2025-01-01",
                score=9.0,
                source="manual",
            )

            assert result["success"] is True
            mock_core.storage.add_entries.assert_called_once()
            call_args = mock_core.storage.add_entries.call_args[0][0]
            assert len(call_args) == 1
            entry = call_args[0]
            assert entry[0] == "http://malicious.com"
            assert entry[1] == "192.168.1.1"
            assert entry[3] == 9.0
            assert entry[4] == "manual"

    @pytest.mark.asyncio
    async def test_add_entry_with_defaults(self):
        """Test add_entry with default parameters."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            result = await add_entry(url="http://malicious.com")

            assert result["success"] is True
            mock_core.storage.add_entries.assert_called_once()
            call_args = mock_core.storage.add_entries.call_args[0][0]
            entry = call_args[0]
            assert entry[0] == "http://malicious.com"
            assert entry[1] is None  # Default IP
            assert entry[3] == 8.0  # Default score
            assert entry[4] == "manual"  # Default source

    @pytest.mark.asyncio
    async def test_add_entry_generates_timestamp(self):
        """Test that add_entry generates a timestamp if not provided."""
        with patch("sec_mcp.mcp_server.core") as mock_core, patch(
            "sec_mcp.mcp_server.datetime"
        ) as mock_datetime:
            mock_now = Mock()
            mock_now.isoformat.return_value = "2025-01-01T12:00:00"
            mock_datetime.now.return_value = mock_now

            await add_entry(url="http://test.com", date=None)

            mock_core.storage.add_entries.assert_called_once()


class TestRemoveEntry:
    """Tests for the remove_entry tool."""

    @pytest.mark.asyncio
    async def test_remove_entry_success(self):
        """Test successful entry removal."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.remove_entry.return_value = True

            result = await remove_entry(value="http://malicious.com")

            assert result["success"] is True
            mock_core.storage.remove_entry.assert_called_once_with("http://malicious.com")

    @pytest.mark.asyncio
    async def test_remove_entry_not_found(self):
        """Test entry removal when entry doesn't exist."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.remove_entry.return_value = False

            result = await remove_entry(value="http://notfound.com")

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_remove_entry_by_ip(self):
        """Test removing entry by IP address."""
        with patch("sec_mcp.mcp_server.core") as mock_core:
            mock_core.storage.remove_entry.return_value = True

            result = await remove_entry(value="192.168.1.1")

            assert result["success"] is True
            mock_core.storage.remove_entry.assert_called_once_with("192.168.1.1")
