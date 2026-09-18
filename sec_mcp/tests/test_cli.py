import json
import os
import subprocess
import sysconfig

import pytest
from click.testing import CliRunner

from sec_mcp.cli import cli, core
from sec_mcp.storage import Storage


def _sec_mcp_bin():
    name = "sec-mcp.exe" if os.name == "nt" else "sec-mcp"
    path = os.path.join(sysconfig.get_path("scripts"), name)
    assert os.path.exists(path), f"sec-mcp executable not found at {path}"
    return path


def _run_cli(*args):
    return subprocess.run(
        [_sec_mcp_bin(), *args],
        capture_output=True, text=True, env=os.environ.copy()) # Pass environment


@pytest.mark.parametrize("command,value", [
    ("check", "example.com"),
    ("check-domain", "example.com"),
    ("check-url", "https://example.com/path"),
    ("check-ip", "1.2.3.4"),
])
def test_check_commands_emit_json(command, value):
    result = CliRunner().invoke(cli, [command, value, "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data["is_safe"], bool)
    assert isinstance(data["explain"], str)


def test_check_domain_json_reflects_blacklist(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path / "cli.db"))
    storage.add_entries(
        [("https://sec-mcp-cli.test/", None, "2026-01-01 00:00:00", 8.0, "pytest")])
    monkeypatch.setattr(core, "storage", storage)
    result = CliRunner().invoke(cli, ["check-domain", "sec-mcp-cli.test", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "is_safe": False, "explain": "Blacklisted domain by pytest"}


@pytest.mark.parametrize("command,value", [
    ("check", "example.com"),
    ("check-domain", "example.com"),
    ("check-url", "https://example.com/path"),
    ("check-ip", "1.2.3.4"),
])
def test_cli_check_subprocess(command, value):
    result = _run_cli(command, value, '--json')
    assert result.returncode == 0, f"CLI {command} failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert isinstance(data["is_safe"], bool)
    assert isinstance(data["explain"], str)


def test_cli_status():
    result = _run_cli('status', '--json')
    assert result.returncode == 0, f"CLI status failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert isinstance(data["entry_count"], int)
    assert isinstance(data["last_update"], str)


def test_cli_batch(tmp_path):
    batch_file = tmp_path / "batch.txt"
    batch_file.write_text('https://example.com\nhttps://test.com\n')
    result = _run_cli('batch', str(batch_file), '--json')
    assert result.returncode == 0, f"CLI batch failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert len(data) == 2
    assert all(isinstance(entry["is_safe"], bool) for entry in data)
