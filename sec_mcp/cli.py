import click
from .sec_mcp import SecMCP

# Global SecMCP instance for CLI
core = SecMCP()

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

@cli.command(help="Update blacklist feeds immediately.")
@click.option('--json', is_flag=True, help='Output minimal JSON confirmation')
def update(json):
    """Force an immediate update of all blacklists."""
    core.update()
    if json:
        import json as _json
        click.echo(_json.dumps({"updated": True}))
    else:
        click.echo("Blacklist update triggered.")

@cli.command(help="Sample random blacklist entries for testing.")
@click.option('-n', '--count', default=10, help='Number of entries to sample')
def sample(count: int):
    """Output a random sample of blacklist values for quick tests."""
    entries = core.sample(count)
    for value in entries:
        click.echo(value)
