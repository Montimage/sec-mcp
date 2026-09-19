import json as _json
import threading

import click

from .sec_mcp import SecMCP
from .utility import package_version

# Shared SecMCP instance for the CLI, created lazily on first use: importing
# this module must stay side-effect free — constructing SecMCP creates the
# SQLite database, opens the log file and starts the scheduler thread.
_core = None
_core_lock = threading.Lock()


def get_core() -> SecMCP:
    """Return the shared SecMCP instance, creating it on first call."""
    global _core
    if _core is None:
        with _core_lock:
            if _core is None:
                _core = SecMCP()
    return _core


def __getattr__(name: str):
    # PEP 562: keep `from sec_mcp.cli import core` working — the name resolves
    # to the lazily-created shared instance instead of a module-level object.
    if name == "core":
        return get_core()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

@click.group()
@click.version_option(version=package_version(), message="%(version)s (MCP Client)")
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
    core = get_core()
    result = core.check(value)
    if json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        if result.blacklisted:
            click.secho("Status: Blacklisted", fg="red")
        else:
            click.secho("Status: Safe", fg="green")
        click.echo(f"Explanation: {result.explanation}")

@cli.command(help="Check a domain (and its parent domains) against the blacklist.")
@click.argument('domain')
@click.option('--json', is_flag=True, help='Output in JSON format')
def check_domain(domain: str, json: bool):
    core = get_core()
    result = core.check_domain(domain)
    if json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        if result.blacklisted:
            click.secho("Status: Blacklisted", fg="red")
        else:
            click.secho("Status: Safe", fg="green")
        click.echo(f"Explanation: {result.explanation}")

@cli.command(help="Check a URL against the blacklist (exact match and its domain).")
@click.argument('url')
@click.option('--json', is_flag=True, help='Output in JSON format')
def check_url(url: str, json: bool):
    core = get_core()
    result = core.check_url(url)
    if json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        if result.blacklisted:
            click.secho("Status: Blacklisted", fg="red")
        else:
            click.secho("Status: Safe", fg="green")
        click.echo(f"Explanation: {result.explanation}")

@cli.command(help="Check an IP address against the blacklist.")
@click.argument('ip')
@click.option('--json', is_flag=True, help='Output in JSON format')
def check_ip(ip: str, json: bool):
    core = get_core()
    result = core.check_ip(ip)
    if json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        if result.blacklisted:
            click.secho("Status: Blacklisted", fg="red")
        else:
            click.secho("Status: Safe", fg="green")
        click.echo(f"Explanation: {result.explanation}")

@cli.command(help="Check multiple inputs from a file against the blacklist.\n\nExample: mcp batch urls.txt --json")
@click.argument('file', type=click.Path(exists=True))
@click.option('--json', is_flag=True, help='Output in JSON format')
def batch(file: str, json: bool):
    core = get_core()
    with open(file) as f:
        values = [line.strip() for line in f if line.strip()]
    results = core.check_batch(values)
    if json:
        click.echo(_json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for value, result in zip(values, results):
            click.secho(f"{value}:", bold=True)
            if result.blacklisted:
                click.secho("  Status: Blacklisted", fg="red")
            else:
                click.secho("  Status: Safe", fg="green")
            click.echo(f"  Explanation: {result.explanation}")

@cli.command(help="Show blacklist status (entry count, last update, sources).\n\nExample: mcp status --json")
@click.option('--json', is_flag=True, help='Output in JSON format')
def status(json):
    core = get_core()
    status = core.get_status()
    source_counts = core.storage.get_source_counts()
    source_type_counts = core.storage.get_source_type_counts()
    if json:
        data = status.to_dict()
        data['source_counts'] = source_counts
        data['source_type_counts'] = source_type_counts
        click.echo(_json.dumps(data, indent=2))
    else:
        click.secho(f"Total entries: {status.entry_count}", bold=True)
        click.echo(f"Last update: {status.last_update}")
        click.echo("Active sources:")
        for source in status.sources:
            count = source_counts.get(source, 0)
            click.echo(f"  - {source}: {count} entries")
        click.echo("\nPer-source breakdown:")
        # Print header
        click.echo(f"{'Source':18} {'Domains':>10} {'URLs':>10} {'IPs':>10}")
        click.echo(f"{'-'*50}")
        for src in sorted(source_type_counts):
            d = source_type_counts[src].get('domain', 0)
            u = source_type_counts[src].get('url', 0)
            i = source_type_counts[src].get('ip', 0)
            click.echo(f"{src:18} {d:10} {u:10} {i:10}")
        click.echo(f"\nServer status: {status.server_status}")

@cli.command(help="Update blacklist feeds immediately.")
@click.option('--json', is_flag=True, help='Output minimal JSON confirmation')
def update(json):
    """Force an immediate update of all blacklists."""
    core = get_core()
    result = core.update() or {"updated": True}
    if json:
        click.echo(_json.dumps(result))
    elif result.get("updated"):
        click.echo("Blacklist update triggered.")
    else:
        click.echo(f"Blacklist update skipped: {result.get('reason', 'rate limited')}")

@cli.command(help="Clear the in-memory URL/IP cache.")
@click.option('--json', is_flag=True, help='Output in JSON format')
def flush_cache(json):
    core = get_core()
    cleared = core.storage.flush_cache()
    if json:
        click.echo(_json.dumps({"cleared": cleared}))
    else:
        if cleared:
            click.secho("In-memory cache cleared.", fg="green")
        else:
            click.secho("Cache was already empty or could not be cleared.", fg="yellow")

@cli.command(help="Sample random blacklist entries for testing.")
@click.option('-n', '--count', default=10, help='Number of entries to sample')
def sample(count: int):
    """Output a random sample of blacklist values for quick tests."""
    core = get_core()
    entries = core.sample(count)
    for value in entries:
        click.echo(value)
