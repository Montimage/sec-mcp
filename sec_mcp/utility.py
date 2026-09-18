"""Utility functions for validation, logging, and configuration management."""

import importlib.metadata
import ipaddress
import json
import logging
import os
import re
import threading
import tomllib
from pathlib import Path
from typing import Any, Dict

import idna
from platformdirs import user_log_dir

_logging_lock = threading.Lock()
_file_handler = None


def package_version() -> str:
    """Resolve the package version: installed metadata first, pyproject.toml in a source tree."""
    try:
        return importlib.metadata.version("sec-mcp")
    except importlib.metadata.PackageNotFoundError:
        pass
    try:
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError):
        return "0.0.0+unknown"


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the MCP client and server."""
    global _file_handler
    level = getattr(logging, log_level)
    with _logging_lock:
        # Configure console output
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        # Replace only the file handler we installed; unrelated user
        # handlers are never touched.
        root_logger = logging.getLogger()
        if _file_handler is not None:
            root_logger.removeHandler(_file_handler)
            _file_handler.close()
            _file_handler = None
        log_path = Path(
            os.environ.get("MCP_LOG_PATH")
            or Path(user_log_dir("sec-mcp", "montimage")) / "mcp-server.log"
        )
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path)
        except OSError as e:
            root_logger.warning(f"Cannot open log file {log_path}: {e}")
        else:
            file_handler.setLevel(level)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            root_logger.addHandler(file_handler)
            _file_handler = file_handler
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
