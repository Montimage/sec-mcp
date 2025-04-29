"""
MCP Client - A Python library and CLI for checking domains, URLs, and IPs against blacklists.
"""

from .sec_mcp import SecMCP, CheckResult, StatusInfo
from .cli import cli
from .utility import validate_input, setup_logging

__version__ = "0.2.4"
__all__ = ['SecMCP', 'CheckResult', 'StatusInfo', 'cli', 'validate_input', 'setup_logging']
