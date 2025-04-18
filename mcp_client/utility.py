"""Utility functions for validation, logging, and configuration management."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict
import idna

def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the MCP client."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)

def validate_input(value: str) -> bool:
    """Validate if a string is a valid domain, URL, or IP address."""
    # URL validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    # IP address validation
    ip_pattern = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
    
    # Check URL
    if url_pattern.match(value):
        return True
    
    # Check IP
    if ip_pattern.match(value):
        return True
    
    # Check domain (IDNA)
    try:
        # Remove protocol if present
        if '://' in value:
            value = value.split('://', 1)[1]
        # Remove path if present
        value = value.split('/', 1)[0]
        # Validate IDNA domain
        idna.encode(value)
        return True
    except (idna.IDNAError, UnicodeError):
        return False
    
    return False
