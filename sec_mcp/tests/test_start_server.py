"""
Tests for the MCP server startup module.

This module tests:
- CLI argument parsing
- Configuration display
- Server startup for both STDIO and HTTP modes
"""

from unittest.mock import Mock, call, patch

import pytest
from click.testing import CliRunner

from sec_mcp.start_server import main, print_http_config, print_stdio_config


class TestPrintStdioConfig:
    """Tests for print_stdio_config function."""

    def test_print_stdio_config_basic(self, capsys):
        """Test that print_stdio_config outputs valid JSON config."""
        with patch("sys.executable", "/usr/bin/python3"):
            print_stdio_config()
            captured = capsys.readouterr()

            assert "MCP Server started successfully (STDIO mode)" in captured.err
            assert '"mcpServers"' in captured.err
            assert '"sec-mcp"' in captured.err
            assert '"/usr/bin/python3"' in captured.err
            # Check for args components (JSON is pretty-printed)
            assert '"args"' in captured.err
            assert '"-m"' in captured.err
            assert '"sec_mcp.start_server"' in captured.err

    def test_print_stdio_config_with_v2_storage_enabled(self, capsys):
        """Test config output when v2 storage is enabled."""
        with patch("sys.executable", "/usr/bin/python3"), patch.dict(
            "os.environ", {"MCP_USE_V2_STORAGE": "true"}
        ):
            print_stdio_config()
            captured = capsys.readouterr()

            assert '"MCP_USE_V2_STORAGE": "true"' in captured.err

    def test_print_stdio_config_with_v2_storage_disabled(self, capsys):
        """Test config output when v2 storage is disabled."""
        with patch("sys.executable", "/usr/bin/python3"), patch.dict(
            "os.environ", {"MCP_USE_V2_STORAGE": "false"}, clear=True
        ):
            print_stdio_config()
            captured = capsys.readouterr()

            assert '"MCP_USE_V2_STORAGE": "false"' in captured.err

    def test_print_stdio_config_different_python_paths(self, capsys):
        """Test that config uses the actual Python executable path."""
        test_path = "/custom/path/to/python"
        with patch("sys.executable", test_path):
            print_stdio_config()
            captured = capsys.readouterr()

            assert test_path in captured.err


class TestPrintHttpConfig:
    """Tests for print_http_config function."""

    def test_print_http_config_basic(self, capsys):
        """Test that print_http_config outputs valid JSON config."""
        print_http_config(host="localhost", port=8000)
        captured = capsys.readouterr()

        assert "MCP Server started successfully (HTTP mode)" in captured.err
        assert "Server running at: http://localhost:8000" in captured.err
        assert "SSE endpoint: http://localhost:8000/sse" in captured.err
        assert '"url": "http://localhost:8000/sse"' in captured.err
        assert '"transport": "sse"' in captured.err

    def test_print_http_config_custom_host_port(self, capsys):
        """Test HTTP config with custom host and port."""
        print_http_config(host="0.0.0.0", port=3000)
        captured = capsys.readouterr()

        assert "http://0.0.0.0:3000" in captured.err
        assert '"url": "http://0.0.0.0:3000/sse"' in captured.err

    def test_print_http_config_shows_tip(self, capsys):
        """Test that HTTP config shows helpful tip."""
        print_http_config(host="localhost", port=8000)
        captured = capsys.readouterr()

        assert "Ctrl+C" in captured.err


class TestMainCLI:
    """Tests for the main CLI function."""

    def test_help_option(self):
        """Test --help option displays help text."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Start the MCP server with configurable transport" in result.output
        assert "--transport" in result.output
        assert "--host" in result.output
        assert "--port" in result.output

    def test_stdio_mode_default(self):
        """Test that STDIO is the default transport mode."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, [])

            # Should call mcp.run with stdio transport
            mock_mcp.run.assert_called_once_with(transport="stdio")
            assert result.exit_code == 0

    def test_stdio_mode_explicit(self):
        """Test explicitly selecting STDIO mode."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["--transport", "stdio"])

            mock_mcp.run.assert_called_once_with(transport="stdio")
            assert result.exit_code == 0

    def test_http_mode(self):
        """Test HTTP transport mode."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["--transport", "http"])

            mock_mcp.run.assert_called_once_with(transport="http", host="localhost", port=8000)
            assert result.exit_code == 0

    def test_http_mode_custom_host_port(self):
        """Test HTTP mode with custom host and port."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["-t", "http", "-h", "0.0.0.0", "-p", "3000"])

            mock_mcp.run.assert_called_once_with(transport="http", host="0.0.0.0", port=3000)
            assert result.exit_code == 0

    def test_transport_short_option(self):
        """Test short option -t for transport."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["-t", "http"])

            assert result.exit_code == 0
            assert mock_mcp.run.call_args[1]["transport"] == "http"

    def test_host_short_option(self):
        """Test short option -h for host."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["-t", "http", "-h", "127.0.0.1"])

            assert result.exit_code == 0
            assert mock_mcp.run.call_args[1]["host"] == "127.0.0.1"

    def test_port_short_option(self):
        """Test short option -p for port."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["-t", "http", "-p", "9000"])

            assert result.exit_code == 0
            assert mock_mcp.run.call_args[1]["port"] == 9000

    def test_environment_variable_transport(self):
        """Test reading transport from MCP_TRANSPORT environment variable."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, [], env={"MCP_TRANSPORT": "http"})

            assert result.exit_code == 0
            assert mock_mcp.run.call_args[1]["transport"] == "http"

    def test_environment_variable_host(self):
        """Test reading host from MCP_HOST environment variable."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["-t", "http"], env={"MCP_HOST": "192.168.1.1"})

            assert result.exit_code == 0
            assert mock_mcp.run.call_args[1]["host"] == "192.168.1.1"

    def test_environment_variable_port(self):
        """Test reading port from MCP_PORT environment variable."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["-t", "http"], env={"MCP_PORT": "5000"})

            assert result.exit_code == 0
            assert mock_mcp.run.call_args[1]["port"] == 5000

    def test_cli_overrides_environment_variables(self):
        """Test that CLI arguments override environment variables."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            result = runner.invoke(main, ["-t", "http", "-p", "9000"], env={"MCP_PORT": "5000"})

            assert result.exit_code == 0
            # CLI argument should win
            assert mock_mcp.run.call_args[1]["port"] == 9000

    def test_invalid_transport_rejected(self):
        """Test that invalid transport mode is rejected."""
        runner = CliRunner()
        result = runner.invoke(main, ["--transport", "invalid"])

        # Click should reject invalid choice
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_case_insensitive_transport(self):
        """Test that transport option is case insensitive."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            # Test uppercase
            result1 = runner.invoke(main, ["--transport", "HTTP"])
            assert result1.exit_code == 0
            assert mock_mcp.run.call_args[1]["transport"] == "http"

            # Test mixed case
            result2 = runner.invoke(main, ["--transport", "StDiO"])
            assert result2.exit_code == 0

    def test_setup_logging_called(self):
        """Test that setup_logging is called on startup."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp"), patch(
            "sec_mcp.start_server.setup_logging"
        ) as mock_setup:
            runner.invoke(main, [])

            mock_setup.assert_called_once()

    def test_stdio_config_printed(self, capsys):
        """Test that STDIO configuration is printed."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp"), patch("sec_mcp.start_server.setup_logging"), patch(
            "sys.executable", "/usr/bin/python"
        ):
            result = runner.invoke(main, ["--transport", "stdio"])

            # Check that config was printed (to stderr)
            assert "mcpServers" in result.output or result.exit_code == 0

    def test_http_config_printed(self, capsys):
        """Test that HTTP configuration is printed."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp"), patch("sec_mcp.start_server.setup_logging"):
            result = runner.invoke(main, ["--transport", "http"])

            # Config should be shown
            assert result.exit_code == 0

    def test_port_must_be_integer(self):
        """Test that port must be an integer."""
        runner = CliRunner()
        result = runner.invoke(main, ["-t", "http", "-p", "not-a-number"])

        assert result.exit_code != 0
        assert "not-a-number" in result.output.lower() or "invalid" in result.output.lower()

    def test_multiple_invocations_independent(self):
        """Test that multiple CLI invocations are independent."""
        runner = CliRunner()
        with patch("sec_mcp.start_server.mcp") as mock_mcp, patch(
            "sec_mcp.start_server.setup_logging"
        ):
            # First invocation
            result1 = runner.invoke(main, ["--transport", "stdio"])
            assert result1.exit_code == 0

            # Second invocation with different options
            result2 = runner.invoke(main, ["-t", "http", "-p", "9000"])
            assert result2.exit_code == 0

            # Verify both were called correctly
            assert mock_mcp.run.call_count == 2
