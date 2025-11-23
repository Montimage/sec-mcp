from datetime import datetime

import anyio
from mcp.server.fastmcp import FastMCP

# import SecMCP for server logic
from .sec_mcp import SecMCP
from .utility import validate_input

# Initialize FastMCP server
mcp = FastMCP("mcp-blacklist")

# Global SecMCP instance for MCP server
core = SecMCP()

# ============================================================================
# CORE TOOLS - Essential functionality only
# ============================================================================


@mcp.tool(
    name="check",
    description="Check domains/URLs/IPs against the blacklist. Accepts single value or list. Returns {value, is_safe, explanation} or list of results.",
)
async def check(values: list[str] | str):
    """Check one or more values against the blacklist."""
    # Handle single value
    if isinstance(values, str):
        values = [values]

    results = []
    for value in values:
        if not validate_input(value):
            results.append(
                {"value": value, "is_safe": False, "explanation": "Invalid input format."}
            )
        else:
            res = core.check(value)
            results.append(
                {"value": value, "is_safe": not res.blacklisted, "explanation": res.explanation}
            )

    # Return single result if single value was provided
    return results[0] if len(results) == 1 and isinstance(values, str) else results


@mcp.tool(
    name="get_status",
    description="Get blacklist status including entry counts and sources. Returns JSON: {entry_count, last_update, sources, server_status, source_counts}.",
)
async def get_status():
    """Return current blacklist status, including per-source entry counts."""
    status = core.get_status()
    source_counts = core.storage.get_source_counts()
    return {
        "entry_count": status.entry_count,
        "last_update": status.last_update,
        "sources": status.sources,
        "server_status": status.server_status,
        "source_counts": source_counts,
    }


@mcp.tool(description="Force immediate update of all blacklists. Returns JSON: {updated: bool}.")
async def update_blacklists():
    """Trigger an immediate blacklist refresh."""
    # Offload to thread to avoid nested event loops
    await anyio.to_thread.run_sync(core.update)
    return {"updated": True}
