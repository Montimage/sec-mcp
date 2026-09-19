import ipaddress
import math
import threading
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

# import SecMCP for server logic
from .sec_mcp import SecMCP
from .utility import validate_input

# Initialize MCP server (SDK v2: FastMCP was renamed to MCPServer)
mcp = MCPServer(name="mcp-blacklist")

# Shared SecMCP instance for the MCP server, created lazily on first use:
# importing this module must stay side-effect free — constructing SecMCP
# creates the SQLite database, opens the log file and starts the scheduler
# thread.
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
    # PEP 562: keep `from sec_mcp.mcp_server import core` working — the name
    # resolves to the lazily-created shared instance instead of a module-level
    # object.
    if name == "core":
        return get_core()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# ============================================================================
# CORE TOOLS - Primary functionality
# ============================================================================

@mcp.tool(name="check_batch", title="Check Batch", description="Check multiple domains/URLs/IPs in one call. Returns list of {value, is_safe, explanation}.",
          annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
async def check_batch(values: List[str]):
    """Check multiple values against the blacklist in a single call."""
    core = get_core()
    results = []
    for value in values:
        if not validate_input(value):
            results.append({"value": value, "is_safe": False, "explanation": "Invalid input format."})
        else:
            res = core.check(value)
            results.append({"value": value, "is_safe": not res.blacklisted, "explanation": res.explanation})
    return results


@mcp.tool(name="get_status", title="Get Status", description="Get blacklist status including entry counts and sources. Returns JSON: {entry_count, last_update, sources, server_status, source_counts}.",
          annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
async def get_status():
    """Return current blacklist status, including per-source entry counts."""
    core = get_core()
    status = core.get_status()
    source_counts = core.storage.get_source_counts()
    return {
        "entry_count": status.entry_count,
        "last_update": status.last_update,
        "sources": status.sources,
        "server_status": status.server_status,
        "source_counts": source_counts
    }


@mcp.tool(title="Update Blacklists", description="Force immediate update of all blacklists. Returns JSON: {updated: bool}.",
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def update_blacklists():
    """Trigger an immediate blacklist refresh."""
    core = get_core()
    # Offload to thread to avoid nested event loops
    await anyio.to_thread.run_sync(core.update)
    return {"updated": True}


# ============================================================================
# DIAGNOSTICS - Consolidated monitoring and debugging
# ============================================================================

@mcp.tool(name="get_diagnostics", title="Get Diagnostics", description="Get diagnostic information. Mode options: 'summary' (default), 'full', 'health', 'performance', 'sample'.",
          annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
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
    core = get_core()

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

_MANUAL_SOURCE = "manual"


@mcp.tool(name="add_entry", title="Add Entry", description="Add a manual blacklist entry.",
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
async def add_entry(url: Optional[str] = None, ip: Optional[str] = None, date: Optional[str] = None, score: float = 8.0, source: str = _MANUAL_SOURCE):
    """Add a manual blacklist entry."""
    if not url and not ip:
        raise ValueError("add_entry requires at least one of 'url' or 'ip'.")
    if url:
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        if not validate_input(url):
            raise ValueError(f"Invalid URL: {url}")
        hostname = urlparse(url).hostname
        if not hostname or not validate_input(hostname):
            raise ValueError(f"Invalid URL host: {url}")
    if ip:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            raise ValueError(f"Invalid IP address: {ip}") from None
    if isinstance(score, bool) or not isinstance(score, (int, float)) \
            or not math.isfinite(score) or not 0 <= score <= 10:
        raise ValueError("score must be a finite number between 0 and 10.")
    ts = date or datetime.now().isoformat(sep=' ', timespec='seconds')
    get_core().storage.add_entries([(url, ip, ts, score, _MANUAL_SOURCE)])
    return {"success": True}


@mcp.tool(name="remove_entry", title="Remove Entry", description="Remove a blacklist entry by URL or IP.",
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False))
async def remove_entry(value: str):
    """Remove a blacklist entry by URL or IP."""
    success = get_core().storage.remove_entry(value)
    return {"success": success}
