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

# ============================================================================
# CORE TOOLS - Primary functionality
# ============================================================================

@mcp.tool(name="check_batch", description="Check multiple domains/URLs/IPs in one call. Returns list of {value, is_safe, explanation}.")
async def check_batch(values: List[str]):
    """Check multiple values against the blacklist in a single call."""
    results = []
    for value in values:
        if not validate_input(value):
            results.append({"value": value, "is_safe": False, "explanation": "Invalid input format."})
        else:
            res = core.check(value)
            results.append({"value": value, "is_safe": not res.blacklisted, "explanation": res.explanation})
    return results


@mcp.tool(name="get_status", description="Get blacklist status including entry counts and sources. Returns JSON: {entry_count, last_update, sources, server_status, source_counts}.")
async def get_status():
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


# ============================================================================
# DIAGNOSTICS - Consolidated monitoring and debugging
# ============================================================================

@mcp.tool(name="get_diagnostics", description="Get diagnostic information. Mode options: 'summary' (default), 'full', 'health', 'performance', 'sample'.")
async def get_diagnostics(mode: str = "summary", sample_count: int = 10):
    """
    Get diagnostic information about the blacklist system.

    Modes:
    - summary: Entry counts, sources, last update (default)
    - full: All available diagnostic data
    - health: Database and scheduler health status
    - performance: Performance metrics and hit rates (v2 only)
    - sample: Random sample of blacklist entries
    """

    if mode == "health":
        # Health check
        db_ok = True
        try:
            core.storage.count_entries()
        except Exception:
            db_ok = False
        scheduler_alive = True
        last_update = core.get_status().last_update
        return {
            "mode": "health",
            "db_ok": db_ok,
            "scheduler_alive": scheduler_alive,
            "last_update": last_update
        }

    elif mode == "performance":
        # Performance metrics (v2 only)
        if hasattr(core.storage, 'get_metrics'):
            metrics = core.storage.get_metrics()
            return {
                "mode": "performance",
                **metrics
            }
        else:
            return {
                "mode": "performance",
                "error": "Metrics not available",
                "message": "Performance metrics are only available with HybridStorage (v2). Set MCP_USE_V2_STORAGE=true to enable."
            }

    elif mode == "sample":
        # Random sample
        entries = core.sample(sample_count)
        return {
            "mode": "sample",
            "count": len(entries),
            "entries": entries
        }

    elif mode == "full":
        # Full diagnostics - everything
        total = core.storage.count_entries()
        per_source = core.storage.get_source_counts()
        last_updates = core.storage.get_last_update_per_source()
        per_source_detail = core.storage.get_source_type_counts()

        # Health
        db_ok = True
        try:
            core.storage.count_entries()
        except Exception:
            db_ok = False

        # Performance (if available)
        metrics = {}
        if hasattr(core.storage, 'get_metrics'):
            metrics = core.storage.get_metrics()

        return {
            "mode": "full",
            "total_entries": total,
            "per_source": per_source,
            "last_updates": last_updates,
            "per_source_detail": per_source_detail,
            "health": {
                "db_ok": db_ok,
                "scheduler_alive": True
            },
            "performance": metrics if metrics else {"available": False}
        }

    else:  # mode == "summary" or default
        # Summary - basic stats
        total = core.storage.count_entries()
        per_source = core.storage.get_source_counts()
        last_updates = core.storage.get_last_update_per_source()

        return {
            "mode": "summary",
            "total_entries": total,
            "per_source": per_source,
            "last_updates": last_updates
        }


# ============================================================================
# ADMINISTRATIVE - Manual entry management
# ============================================================================

@mcp.tool(name="add_entry", description="Add a manual blacklist entry.")
async def add_entry(url: str, ip: Optional[str] = None, date: Optional[str] = None, score: float = 8.0, source: str = "manual"):
    """Add a manual blacklist entry."""
    ts = date or datetime.now().isoformat(sep=' ', timespec='seconds')
    core.storage.add_entries([(url, ip, ts, score, source)])
    return {"success": True}


@mcp.tool(name="remove_entry", description="Remove a blacklist entry by URL or IP.")
async def remove_entry(value: str):
    """Remove a blacklist entry by URL or IP."""
    success = core.storage.remove_entry(value)
    return {"success": success}
