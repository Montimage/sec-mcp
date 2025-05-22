import subprocess
import sys
import tempfile
import os
import shutil
from pathlib import Path

def test_cli_check():
    sec_mcp_executable = os.path.join(os.path.dirname(sys.executable), 'sec-mcp')
    assert os.path.exists(sec_mcp_executable), f"sec-mcp executable not found at {sec_mcp_executable}"
    result = subprocess.run([
            sec_mcp_executable, 'check', 'https://example.com', '--json'
        ], capture_output=True, text=True, env=os.environ.copy()) # Pass environment
    assert result.returncode == 0, f"CLI check failed: {result.stderr}"
    assert 'is_safe' in result.stdout

def test_cli_status():
    sec_mcp_executable = os.path.join(os.path.dirname(sys.executable), 'sec-mcp')
    result = subprocess.run([
            sec_mcp_executable, 'status', '--json'
        ], capture_output=True, text=True, env=os.environ.copy())
    assert result.returncode == 0, f"CLI status failed: {result.stderr}"
    assert 'entry_count' in result.stdout

# For batch, create a temp file

def test_cli_batch():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        f.write('https://example.com\nhttps://test.com\n')
        f.flush()
        sec_mcp_executable = os.path.join(os.path.dirname(sys.executable), 'sec-mcp')
        result = subprocess.run([
            sec_mcp_executable, 'batch', f.name, '--json'
        ], capture_output=True, text=True, env=os.environ.copy())
        assert result.returncode == 0, f"CLI batch failed: {result.stderr}"
        assert 'is_safe' in result.stdout
    Path(f.name).unlink()
