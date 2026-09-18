"""Test the utility functions."""
import logging
import threading

from sec_mcp import utility
from sec_mcp.utility import load_config, setup_logging, validate_input


def test_validate_url():
    """Test URL validation."""
    assert validate_input("https://example.com")
    assert validate_input("http://sub.domain.com/path")
    assert not validate_input("not-a-url")

def test_validate_ip():
    """Test IP address validation."""
    assert validate_input("192.168.1.1")
    assert not validate_input("256.256.256.256")
    assert not validate_input("192.168.1")

def test_validate_domain():
    """Test domain validation."""
    assert validate_input("example.com")
    assert validate_input("sub.domain.co.uk")
    assert validate_input("xn--bcher-kva.com")  # IDN domain
    assert not validate_input("invalid..com")

def test_load_config():
    """Test configuration loading."""
    config = load_config()
    assert isinstance(config, dict)
    assert "blacklist_sources" in config
    assert "update_time" in config
    assert "cache_size" in config

def test_setup_logging():
    """Test logging configuration."""
    setup_logging("DEBUG")
    logger = logging.getLogger("sec_mcp")
    assert logger.level == logging.DEBUG


def _owned_handlers():
    fh = utility._file_handler
    return [fh] if fh is not None and fh in logging.getLogger().handlers else []


def _remove_owned_handlers():
    fh = utility._file_handler
    if fh is not None:
        logging.getLogger().removeHandler(fh)
        fh.close()
        utility._file_handler = None


def test_setup_logging_twice_keeps_one_owned_handler(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_LOG_PATH", str(tmp_path / "test.log"))
    sentinel = logging.FileHandler(tmp_path / "user.log")
    logging.getLogger().addHandler(sentinel)
    try:
        setup_logging()
        setup_logging()
        owned = _owned_handlers()
        assert len(owned) == 1
        assert owned[0].baseFilename == str(tmp_path / "test.log")
        assert sentinel in logging.getLogger().handlers
    finally:
        logging.getLogger().removeHandler(sentinel)
        sentinel.close()
        _remove_owned_handlers()


def test_setup_logging_defaults_to_platformdirs(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_LOG_PATH", raising=False)
    monkeypatch.setattr(
        "sec_mcp.utility.user_log_dir", lambda *a, **kw: str(tmp_path / "logs"))
    try:
        setup_logging()
        owned = _owned_handlers()
        assert len(owned) == 1
        assert owned[0].baseFilename == str(tmp_path / "logs" / "mcp-server.log")
    finally:
        _remove_owned_handlers()


def test_setup_logging_concurrent_calls_leave_one_handler(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_LOG_PATH", str(tmp_path / "t.log"))
    try:
        threads = [threading.Thread(target=setup_logging) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(_owned_handlers()) == 1
    finally:
        _remove_owned_handlers()


def test_setup_logging_survives_unwritable_log_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_LOG_PATH", str(tmp_path / "x.log"))

    def raising(*a, **kw):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(logging, "FileHandler", raising)
    try:
        setup_logging()
        assert utility._file_handler is None
    finally:
        _remove_owned_handlers()
