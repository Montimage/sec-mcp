"""Regression tests for issue #33: importing sec_mcp must be side-effect free.

`import sec_mcp`, `import sec_mcp.cli` and `import sec_mcp.mcp_server` must not
create files (SQLite database, log file, feed cache) or start threads (the
update scheduler). SecMCP construction is deferred to the entry points that
need it via each module's `get_core()`.
"""

import importlib
import os
import subprocess
import sys


def _import_probe_env(tmp_path):
    """Env that redirects every artifact the package could emit into tmp_path.

    The scheduler stays enabled (MCP_DISABLE_SCHEDULER removed) so a stray
    import-time thread would be caught by the probe's thread count.
    """
    env = os.environ.copy()
    env["MCP_DB_PATH"] = str(tmp_path / "probe.db")
    env["MCP_LOG_PATH"] = str(tmp_path / "probe.log")
    env["MCP_CACHE_DIR"] = str(tmp_path / "cache")
    env.pop("MCP_DISABLE_SCHEDULER", None)
    return env


def test_package_import_creates_no_files_or_threads(tmp_path):
    """The exact acceptance criterion: import exits 0, creates no file,
    starts no thread (threading.active_count() == 1)."""
    probe = (
        "import sys, threading\n"
        "import sec_mcp, sec_mcp.cli, sec_mcp.mcp_server\n"
        "sys.exit(0 if threading.active_count() == 1 else 3)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        env=_import_probe_env(tmp_path),
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_package_import_survives_unwritable_db_path(tmp_path):
    """A db path inside a regular file can never be created — the import must
    not touch it at all (previously exited non-zero from Storage's makedirs,
    matching the issue's MCP_DB_PATH=/nonexistent/x probe)."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    env = _import_probe_env(tmp_path)
    env["MCP_DB_PATH"] = str(blocker / "x.db")
    result = subprocess.run(
        [sys.executable, "-c", "import sec_mcp, sec_mcp.cli, sec_mcp.mcp_server"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert blocker.read_text() == "not a directory"


def test_get_core_is_a_lazy_singleton():
    """Each entry-point module exposes one lazily-created shared instance, and
    the legacy `core` module attribute still resolves to it (PEP 562)."""
    # import_module, not `from sec_mcp import cli`: the package attribute `cli`
    # is the click Group, which shadows the submodule.
    cli = importlib.import_module("sec_mcp.cli")
    mcp_server = importlib.import_module("sec_mcp.mcp_server")
    from sec_mcp.sec_mcp import SecMCP

    for module in (cli, mcp_server):
        instance = module.get_core()
        assert isinstance(instance, SecMCP)
        assert module.get_core() is instance
        assert module.core is instance
