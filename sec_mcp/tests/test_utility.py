"""Test the utility functions."""
import logging

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
    return [h for h in logging.getLogger().handlers if getattr(h, "_sec_mcp_owned", False)]


def _remove_owned_handlers():
    root = logging.getLogger()
    for h in root.handlers[:]:
        if getattr(h, "_sec_mcp_owned", False):
            root.removeHandler(h)
            h.close()


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
