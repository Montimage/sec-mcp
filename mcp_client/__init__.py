"""
MCP Client - A Python library and CLI for checking domains, URLs, and IPs against blacklists.
"""

from .core import Core, CheckResult, StatusInfo
from .interface import cli
from .utility import validate_input, setup_logging

__version__ = "0.1.0"
__all__ = ['Core', 'CheckResult', 'StatusInfo', 'cli', 'validate_input', 'setup_logging']
