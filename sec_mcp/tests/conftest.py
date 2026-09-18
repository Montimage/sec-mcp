"""Session-wide hermetic environment for the test suite.

`import sec_mcp` instantiates `SecMCP()` at module level (cli.py), which
resolves MCP_DB_PATH/MCP_LOG_PATH/MCP_DISABLE_SCHEDULER at that moment — so
they are set here, before pytest imports any test module. Every artifact the
package can emit is redirected to temporary storage so a suite run leaves no
trace in the repository.
"""

import os
import tempfile

import pytest

_TEST_TMP = tempfile.mkdtemp(prefix="sec_mcp_tests_")

os.environ["MCP_DB_PATH"] = os.path.join(_TEST_TMP, "test.db")
os.environ["MCP_LOG_PATH"] = os.path.join(_TEST_TMP, "mcp-server.log")
os.environ["MCP_DISABLE_SCHEDULER"] = "1"


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Give each test a private working directory.

    CWD-relative writes (`test_storage_sec_mcp.db*` and the literal
    `:memory:` file produced by Storage's abspath) land in tmp_path
    instead of the repository root; the feed cache is redirected to
    tmp_path/downloads via MCP_CACHE_DIR.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "downloads"))
