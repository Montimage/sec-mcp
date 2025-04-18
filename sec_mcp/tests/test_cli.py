import subprocess
import sys
from pathlib import Path

def test_cli_check():
    result = subprocess.run([
        sys.executable, '-m', 'sec_mcp.cli', 'check', 'https://example.com', '--json'
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert 'is_safe' in result.stdout

def test_cli_status():
    result = subprocess.run([
        sys.executable, '-m', 'sec_mcp.cli', 'status', '--json'
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert 'entry_count' in result.stdout

# For batch, create a temp file
import tempfile

def test_cli_batch():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        f.write('https://example.com\nhttps://test.com\n')
        f.flush()
        result = subprocess.run([
            sys.executable, '-m', 'sec_mcp.cli', 'batch', f.name, '--json'
        ], capture_output=True, text=True)
        assert result.returncode == 0
        assert 'is_safe' in result.stdout
    Path(f.name).unlink()
