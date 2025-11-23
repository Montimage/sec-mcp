"""Unit and integration tests for CLI module."""

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from sec_mcp.cli import (
    batch,
    check,
    check_domain,
    check_ip,
    check_url,
    cli,
    flush_cache,
    sample,
    status,
    update,
)
from sec_mcp.sec_mcp import CheckResult, StatusInfo

# ============================================================================
# Integration Tests (using actual subprocess calls)
# ============================================================================


def test_cli_check():
    """Integration test: check command via subprocess."""
    sec_mcp_executable = os.path.join(os.path.dirname(sys.executable), "sec-mcp")
    assert os.path.exists(
        sec_mcp_executable
    ), f"sec-mcp executable not found at {sec_mcp_executable}"
    result = subprocess.run(
        [sec_mcp_executable, "check", "https://example.com", "--json"],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, f"CLI check failed: {result.stderr}"
    assert "is_safe" in result.stdout


def test_cli_status():
    """Integration test: status command via subprocess."""
    sec_mcp_executable = os.path.join(os.path.dirname(sys.executable), "sec-mcp")
    result = subprocess.run(
        [sec_mcp_executable, "status", "--json"],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, f"CLI status failed: {result.stderr}"
    assert "entry_count" in result.stdout


def test_cli_batch():
    """Integration test: batch command via subprocess."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write("https://example.com\nhttps://test.com\n")
        f.flush()
        sec_mcp_executable = os.path.join(os.path.dirname(sys.executable), "sec-mcp")
        result = subprocess.run(
            [sec_mcp_executable, "batch", f.name, "--json"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        assert result.returncode == 0, f"CLI batch failed: {result.stderr}"
        assert "is_safe" in result.stdout
    Path(f.name).unlink()


# ============================================================================
# Unit Tests (using Click CliRunner and mocks)
# ============================================================================


class TestCheckCommand:
    """Unit tests for check command."""

    def test_check_blacklisted_json(self):
        """Test check command with blacklisted result in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check.return_value = CheckResult(
                blacklisted=True, explanation="Blacklisted by TestSource"
            )
            result = runner.invoke(check, ["evil.com", "--json"])
            assert result.exit_code == 0
            # CLI outputs Python dict repr, not JSON
            output = ast.literal_eval(result.output.strip())
            assert output["is_safe"] is False
            assert "TestSource" in output["explain"]

    def test_check_safe_json(self):
        """Test check command with safe result in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check.return_value = CheckResult(
                blacklisted=False, explanation="Not blacklisted"
            )
            result = runner.invoke(check, ["safe.com", "--json"])
            assert result.exit_code == 0
            # CLI outputs Python dict repr, not JSON
            output = ast.literal_eval(result.output.strip())
            assert output["is_safe"] is True

    def test_check_blacklisted_text(self):
        """Test check command with blacklisted result in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check.return_value = CheckResult(
                blacklisted=True, explanation="Blacklisted by TestSource"
            )
            result = runner.invoke(check, ["evil.com"])
            assert result.exit_code == 0
            assert "Blacklisted" in result.output
            assert "TestSource" in result.output

    def test_check_safe_text(self):
        """Test check command with safe result in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check.return_value = CheckResult(
                blacklisted=False, explanation="Not blacklisted"
            )
            result = runner.invoke(check, ["safe.com"])
            assert result.exit_code == 0
            assert "Safe" in result.output


class TestCheckDomainCommand:
    """Unit tests for check_domain command."""

    def test_check_domain_json(self):
        """Test check_domain command in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check_domain.return_value = CheckResult(
                blacklisted=True, explanation="Domain blacklisted"
            )
            result = runner.invoke(check_domain, ["evil.com", "--json"])
            assert result.exit_code == 0
            output = ast.literal_eval(result.output.strip())
            assert output["is_safe"] is False

    def test_check_domain_text(self):
        """Test check_domain command in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check_domain.return_value = CheckResult(
                blacklisted=False, explanation="Domain safe"
            )
            result = runner.invoke(check_domain, ["safe.com"])
            assert result.exit_code == 0
            assert "Safe" in result.output


class TestCheckURLCommand:
    """Unit tests for check_url command."""

    def test_check_url_json(self):
        """Test check_url command in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check_url.return_value = CheckResult(
                blacklisted=True, explanation="URL blacklisted"
            )
            result = runner.invoke(check_url, ["http://evil.com/malware", "--json"])
            assert result.exit_code == 0
            output = ast.literal_eval(result.output.strip())
            assert output["is_safe"] is False

    def test_check_url_text(self):
        """Test check_url command in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check_url.return_value = CheckResult(
                blacklisted=False, explanation="URL safe"
            )
            result = runner.invoke(check_url, ["http://safe.com"])
            assert result.exit_code == 0
            assert "Safe" in result.output


class TestCheckIPCommand:
    """Unit tests for check_ip command."""

    def test_check_ip_json(self):
        """Test check_ip command in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check_ip.return_value = CheckResult(
                blacklisted=True, explanation="IP blacklisted"
            )
            result = runner.invoke(check_ip, ["192.168.1.100", "--json"])
            assert result.exit_code == 0
            output = ast.literal_eval(result.output.strip())
            assert output["is_safe"] is False

    def test_check_ip_text(self):
        """Test check_ip command in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.check_ip.return_value = CheckResult(blacklisted=False, explanation="IP safe")
            result = runner.invoke(check_ip, ["192.168.1.100"])
            assert result.exit_code == 0
            assert "Safe" in result.output


class TestBatchCommand:
    """Unit tests for batch command."""

    def test_batch_json(self):
        """Test batch command in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core, tempfile.NamedTemporaryFile(
            mode="w", delete=False
        ) as f:
            f.write("evil.com\nsafe.com\n")
            f.flush()

            mock_core.check_batch.return_value = [
                CheckResult(blacklisted=True, explanation="Blacklisted"),
                CheckResult(blacklisted=False, explanation="Safe"),
            ]

            result = runner.invoke(batch, [f.name, "--json"])
            assert result.exit_code == 0
            output = json.loads(result.output)
            assert len(output) == 2
            assert output[0]["is_safe"] is False
            assert output[1]["is_safe"] is True

            Path(f.name).unlink()

    def test_batch_text(self):
        """Test batch command in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core, tempfile.NamedTemporaryFile(
            mode="w", delete=False
        ) as f:
            f.write("evil.com\n")
            f.flush()

            mock_core.check_batch.return_value = [
                CheckResult(blacklisted=True, explanation="Blacklisted"),
            ]

            result = runner.invoke(batch, [f.name])
            assert result.exit_code == 0
            assert "evil.com" in result.output
            assert "Blacklisted" in result.output

            Path(f.name).unlink()


class TestStatusCommand:
    """Unit tests for status command."""

    def test_status_json(self):
        """Test status command in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            from datetime import datetime

            mock_status = StatusInfo(
                entry_count=1000,
                last_update=datetime(2025, 1, 1, 12, 0, 0),
                sources=["OpenPhish", "URLhaus"],
                server_status="Running",
            )
            mock_core.get_status.return_value = mock_status
            mock_core.storage.get_source_counts.return_value = {
                "OpenPhish": 500,
                "URLhaus": 500,
            }
            mock_core.storage.get_source_type_counts.return_value = {
                "OpenPhish": {"domain": 200, "url": 300},
                "URLhaus": {"url": 500},
            }

            result = runner.invoke(status, ["--json"])
            assert result.exit_code == 0
            output = json.loads(result.output)
            assert output["entry_count"] == 1000
            assert "OpenPhish" in output["sources"]

    def test_status_text(self):
        """Test status command in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            from datetime import datetime

            mock_status = StatusInfo(
                entry_count=1000,
                last_update=datetime(2025, 1, 1, 12, 0, 0),
                sources=["OpenPhish"],
                server_status="Running",
            )
            mock_core.get_status.return_value = mock_status
            mock_core.storage.get_source_counts.return_value = {"OpenPhish": 1000}
            mock_core.storage.get_source_type_counts.return_value = {
                "OpenPhish": {"domain": 500, "url": 500}
            }

            result = runner.invoke(status, [])
            assert result.exit_code == 0
            assert "1000" in result.output
            assert "OpenPhish" in result.output


class TestUpdateCommand:
    """Unit tests for update command."""

    def test_update_json(self):
        """Test update command in JSON format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.update.return_value = None
            result = runner.invoke(update, ["--json"])
            assert result.exit_code == 0
            output = json.loads(result.output)
            assert output["updated"] is True
            mock_core.update.assert_called_once()

    def test_update_text(self):
        """Test update command in text format."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.update.return_value = None
            result = runner.invoke(update, [])
            assert result.exit_code == 0
            assert "update triggered" in result.output.lower()
            mock_core.update.assert_called_once()


class TestFlushCacheCommand:
    """Unit tests for flush_cache command."""

    def test_flush_cache_json_cleared(self):
        """Test flush_cache command in JSON format when cache is cleared."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.storage.flush_cache.return_value = True
            result = runner.invoke(flush_cache, ["--json"])
            assert result.exit_code == 0
            output = json.loads(result.output)
            assert output["cleared"] is True

    def test_flush_cache_text_cleared(self):
        """Test flush_cache command in text format when cache is cleared."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.storage.flush_cache.return_value = True
            result = runner.invoke(flush_cache, [])
            assert result.exit_code == 0
            assert "cleared" in result.output.lower()

    def test_flush_cache_text_not_cleared(self):
        """Test flush_cache command in text format when cache is not cleared."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.storage.flush_cache.return_value = False
            result = runner.invoke(flush_cache, [])
            assert result.exit_code == 0
            assert "empty" in result.output.lower() or "could not" in result.output.lower()


class TestSampleCommand:
    """Unit tests for sample command."""

    def test_sample_default_count(self):
        """Test sample command with default count."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.sample.return_value = ["evil1.com", "evil2.com", "evil3.com"]
            result = runner.invoke(sample, [])
            assert result.exit_code == 0
            assert "evil1.com" in result.output
            mock_core.sample.assert_called_once_with(10)

    def test_sample_custom_count(self):
        """Test sample command with custom count."""
        runner = CliRunner()
        with patch("sec_mcp.cli.core") as mock_core:
            mock_core.sample.return_value = ["evil1.com", "evil2.com"]
            result = runner.invoke(sample, ["-n", "2"])
            assert result.exit_code == 0
            assert "evil1.com" in result.output
            mock_core.sample.assert_called_once_with(2)
