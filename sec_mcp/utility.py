"""Utility functions for validation, logging, and configuration management."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict
import idna
import ipaddress

def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the MCP client and server."""
    level = getattr(logging, log_level)
    # Configure console output
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Add file handler for persistent logs
    project_root = Path(__file__).parent.parent
    log_path = project_root / 'mcp-server.log'
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)
    # Set sec_mcp logger level
    logging.getLogger("sec_mcp").setLevel(level)

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)

def validate_input(value: str) -> bool:
    """Validate if a string is a valid domain, URL, or IP address."""
    # URL validation
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}\.?|'
        r'localhost)'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    if url_pattern.match(value):
        return True
    # IP address validation (strict)
    try:
        ip = ipaddress.ip_address(value)
        if ip.version == 4:
            return True
    except ValueError:
        pass
    # Domain validation (must have at least one dot and valid TLD)
    try:
        if '://' in value:
            value = value.split('://', 1)[1]
        value = value.split('/', 1)[0]
        if value.count('.') >= 1 and not value.endswith('.'):
            idna.encode(value)
            tld = value.rsplit('.', 1)[-1]
            if 2 <= len(tld) <= 63 and tld.isalpha():
                return True
    except (idna.IDNAError, UnicodeError):
        return False
    return False
