from typing import Any, Dict, List, Optional
import click
from mcp.server.fastmcp import FastMCP
from .core import Core
from .utility import validate_input

# Initialize FastMCP server
mcp = FastMCP("mcp-blacklist")

class MCPServer:
    def __init__(self, core: Core):
        self.core = core

    @mcp.tool()
    async def check_blacklist(self, value: str) -> Dict[str, Any]:
        """Check if a domain, URL, or IP address is in the blacklist.
        
        Args:
            value: The domain, URL, or IP address to check
            
        Returns:
            A dictionary containing:
                is_safe: bool - True if not in blacklist, False if blacklisted
                explain: str - Explanation of the result
        """
        # Validate input
        if not validate_input(value):
            return {
                "is_safe": False,
                "explain": "Invalid input format. Must be a valid domain, URL, or IP address."
            }
        
        # Check blacklist
        result = self.core.check(value)
        return {
            "is_safe": not result.blacklisted,
            "explain": result.explanation
        }

@click.group()
@click.version_option(version="0.1.0", message="%(version)s (MCP Client)")
def cli():
    """MCP Client CLI for checking domains, URLs, and IPs against blacklists.

    Examples:
      mcp check https://example.com
      mcp batch urls.txt --json
      mcp status
    """
    pass

@cli.command(help="Check a single domain, URL, or IP against the blacklist.\n\nExample: mcp check https://example.com --json")
@click.argument('value')
@click.option('--json', is_flag=True, help='Output in JSON format')
def check(value: str, json: bool):
    core = Core()
    result = core.check(value)
    if json:
        click.echo(result.to_json())
    else:
        if result.blacklisted:
            click.secho(f"Status: Blacklisted", fg="red")
        else:
            click.secho(f"Status: Safe", fg="green")
        click.echo(f"Explanation: {result.explanation}")

@cli.command(help="Check multiple inputs from a file against the blacklist.\n\nExample: mcp batch urls.txt --json")
@click.argument('file', type=click.Path(exists=True))
@click.option('--json', is_flag=True, help='Output in JSON format')
def batch(file: str, json: bool):
    core = Core()
    with open(file) as f:
        values = [line.strip() for line in f if line.strip()]
    results = core.check_batch(values)
    if json:
        import json as _json
        click.echo(_json.dumps([r.to_json() for r in results], indent=2))
    else:
        for value, result in zip(values, results):
            click.secho(f"{value}:", bold=True)
            if result.blacklisted:
                click.secho(f"  Status: Blacklisted", fg="red")
            else:
                click.secho(f"  Status: Safe", fg="green")
            click.echo(f"  Explanation: {result.explanation}")

@cli.command(help="Show blacklist status (entry count, last update, sources).\n\nExample: mcp status --json")
@click.option('--json', is_flag=True, help='Output in JSON format')
def status(json):
    core = Core()
    status = core.get_status()
    if json:
        import json as _json
        click.echo(_json.dumps(status.to_json(), indent=2))
    else:
        click.secho(f"Total entries: {status.entry_count}", bold=True)
        click.echo(f"Last update: {status.last_update}")
        click.echo("Active sources:")
        for source in status.sources:
            click.echo(f"  - {source}")
        click.echo(f"Server status: {status.server_status}")

if __name__ == "__main__":
    # Initialize and run the MCP server
    core = Core()
    server = MCPServer(core)
    mcp.run(transport='stdio')
