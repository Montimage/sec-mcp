from mcp.server.fastmcp import FastMCP
import anyio
# import SecMCP for server logic
from .sec_mcp import SecMCP
from .utility import validate_input
from datetime import datetime
from typing import List, Optional

# Initialize FastMCP server
mcp = FastMCP("mcp-blacklist")

# Global SecMCP instance for MCP server
core = SecMCP()

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

# Bulk check tool
@mcp.tool(name="check_batch", description="Check multiple domains/URLs/IPs in one call. Returns list of {value, is_safe, explanation}.")
async def check_batch(values: List[str]):
    results = []
    for value in values:
        if not validate_input(value):
            results.append({"value": value, "is_safe": False, "explanation": "Invalid input format."})
        else:
            res = core.check(value)
            results.append({"value": value, "is_safe": not res.blacklisted, "explanation": res.explanation})
    return results

# Sample random blacklist entries
@mcp.tool(name="sample_blacklist", description="Return a random sample of blacklist entries.")
async def sample_blacklist(count: int):
    entries = core.sample(count)
    return entries

# Detailed source statistics
@mcp.tool(name="get_source_stats", description="Get per-source entry counts and last update times, including domain/url/ip breakdown.")
async def get_source_stats():
    total = core.storage.count_entries()
    per_source = core.storage.get_source_counts()
    last_updates = core.storage.get_last_update_per_source()
    per_source_detail = core.storage.get_source_type_counts()
    return {
        "total_entries": total,
        "per_source": per_source,
        "last_updates": last_updates,
        "per_source_detail": per_source_detail
    }

# Retrieve update history
@mcp.tool(name="get_update_history", description="Get update history records. Optional filters: source, start, end.")
async def get_update_history(source: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None):
    history = core.storage.get_update_history(source, start, end)
    return history

# Flush in-memory cache
@mcp.tool(name="flush_cache", description="Clear in-memory URL/IP cache.")
async def flush_cache():
    cleared = core.storage.flush_cache()
    return {"cleared": cleared}

# Health check endpoint
@mcp.tool(name="health_check", description="Check database and scheduler health.")
async def health_check():
    db_ok = True
    try:
        core.storage.count_entries()
    except Exception:
        db_ok = False
    scheduler_alive = True
    last_update = core.get_status().last_update
    return {"db_ok": db_ok, "scheduler_alive": scheduler_alive, "last_update": last_update}

# Manual entry tools
@mcp.tool(name="add_entry", description="Add a manual blacklist entry.")
async def add_entry(url: str, ip: Optional[str] = None, date: Optional[str] = None, score: float = 8.0, source: str = "manual"):
    ts = date or datetime.now().isoformat(sep=' ', timespec='seconds')
    core.storage.add_entries([(url, ip, ts, score, source)])
    return {"success": True}

@mcp.tool(name="remove_entry", description="Remove a blacklist entry by URL or IP.")
async def remove_entry(value: str):
    success = core.storage.remove_entry(value)
    return {"success": success}
