"""
MCP Client - A Python library and CLI for checking domains, URLs, and IPs against blacklists.
"""

from .cli import cli
from .sec_mcp import CheckResult, SecMCP, StatusInfo
from .utility import setup_logging, validate_input

__version__ = "0.2.7"
__all__ = ["SecMCP", "CheckResult", "StatusInfo", "cli", "validate_input", "setup_logging"]
