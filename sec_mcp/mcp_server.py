from mcp.server.fastmcp import FastMCP
import anyio
# import SecMCP for server logic
from .sec_mcp import SecMCP
from .utility import validate_input

# Initialize FastMCP server
mcp = FastMCP("mcp-blacklist")

# Global SecMCP instance for MCP server
core = SecMCP()

@mcp.tool(name="check", description="Check if a domain, URL, or IP address is in the blacklist. Returns JSON: {is_safe: bool, explain: str}.")
async def check_blacklist(value: str):
    """Check a single value against the blacklist."""
    if not validate_input(value):
        return {"is_safe": False, "explain": "Invalid input format. Must be a valid domain, URL, or IP address."}
    result = core.check(value)
    return {"is_safe": not result.blacklisted, "explain": result.explanation}

@mcp.tool(description="Get status of the blacklist. Returns JSON: {entry_count: int, last_update: str, sources: List[str], server_status: str, source_counts: dict}.")
async def get_blacklist_status():
    """Return current blacklist status, including per-source entry counts."""
    status = core.get_status()
    source_counts = core.storage.get_source_counts()
    return {
        "entry_count": status.entry_count,
        "last_update": status.last_update,
        "sources": status.sources,
        "server_status": status.server_status,
        "source_counts": source_counts
    }

@mcp.tool(description="Force immediate update of all blacklists. Returns JSON: {updated: bool}.")
async def update_blacklists():
    """Trigger an immediate blacklist refresh."""
    # Offload to thread to avoid nested event loops
    await anyio.to_thread.run_sync(core.update)
    return {"updated": True}
