"""Utility functions for validation, logging, and configuration management."""

import ipaddress
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

import idna
from platformdirs import user_log_dir


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the MCP client and server."""
    level = getattr(logging, log_level)
    # Configure console output
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Add file handler for persistent logs; repeat calls replace only the
    # handler we installed, never unrelated user handlers.
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if getattr(handler, "_sec_mcp_owned", False):
            root_logger.removeHandler(handler)
            handler.close()
    log_path = Path(
        os.environ.get("MCP_LOG_PATH")
        or Path(user_log_dir("sec-mcp", "montimage")) / "mcp-server.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path)
    file_handler._sec_mcp_owned = True
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)
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
