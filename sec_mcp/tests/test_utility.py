"""Test the utility functions."""
import pytest
from sec_mcp.utility import validate_input, load_config, setup_logging
import logging

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
