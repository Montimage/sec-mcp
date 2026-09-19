import ipaddress
import math
import threading
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

# import SecMCP for server logic
from .sec_mcp import SecMCP
from .utility import package_version, validate_input

# Initialize MCP server (SDK v2: FastMCP was renamed to MCPServer).
# The identity fields feed `serverInfo` (initialize + the `server/discover`
# `_meta` stamp) and `instructions` on both handshake paths.
mcp = MCPServer(
    name="sec-mcp",
    version=package_version(),
    title="sec-mcp — Security Blacklist Checker",
    description=(
        "MCP server that checks domains, URLs and IPs against security "
        "blacklists backed by SQLite."
    ),
    website_url="https://github.com/Montimage/sec-mcp",
    instructions=(
        "Use check_batch to screen domains, URLs or IPs against the security "
        "blacklists. get_status reports blacklist freshness and per-source "
        "counts; update_blacklists forces a feed refresh; get_diagnostics "
        "exposes health, performance and sampling modes; add_entry and "
        "remove_entry manage manual entries."
    ),
)

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
# STRUCTURED OUTPUT - typed return models published as tools/list outputSchema
# ============================================================================

# Tri-state verdict for a single checked value.
CheckVerdict = Literal["safe", "blacklisted", "invalid"]


class CheckBatchItem(BaseModel):
    """Result for one value submitted to ``check_batch``."""

    value: str
    is_safe: bool
    verdict: CheckVerdict
    explanation: str


class GetStatusResult(BaseModel):
    """Blacklist status payload returned by ``get_status``."""

    entry_count: int
    last_update: datetime
    sources: List[str]
    server_status: str
    source_counts: Dict[str, int]
    scheduler_alive: bool


class UpdateBlacklistsResult(BaseModel):
    """Acknowledgement returned by ``update_blacklists``.

    ``extra="allow"`` lets the rate-limit refusal carry a ``reason`` key while
    the success payload stays exactly ``{"updated": True}``.
    """

    model_config = ConfigDict(extra="allow")

    updated: bool


class GetDiagnosticsResult(BaseModel):
    """Union of every ``get_diagnostics`` mode payload.

    ``mode`` is always present; the remaining keys are optional because each
    mode returns a different subset. ``extra="allow"`` lets dynamic
    performance-metric keys pass validation and survive into
    ``structuredContent``.
    """

    model_config = ConfigDict(extra="allow")

    mode: str
    db_ok: Optional[bool] = None
    scheduler_alive: Optional[bool] = None
    last_update: Optional[datetime] = None
    error: Optional[str] = None
    message: Optional[str] = None
    count: Optional[int] = None
    entries: Optional[List[str]] = None
    total_entries: Optional[int] = None
    per_source: Optional[Dict[str, int]] = None
    last_updates: Optional[Dict[str, str]] = None
    per_source_detail: Optional[Dict[str, dict]] = None
    health: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None


class AddEntryResult(BaseModel):
    """Acknowledgement returned by ``add_entry``."""

    success: bool


class RemoveEntryResult(BaseModel):
    """Acknowledgement returned by ``remove_entry``."""

    success: bool


def _error_result(exc: Exception) -> CallToolResult:
    """Surface a domain failure as an ``isError`` tool result.

    Returning the result (rather than raising) keeps the message on the wire:
    the SDK only preserves exception text for deliberately raised ToolErrors
    and masks everything else behind a generic crash message.
    """
    return CallToolResult(
        content=[TextContent(type="text", text=str(exc))],
        is_error=True,
    )


# ============================================================================
# CORE TOOLS - Primary functionality
# ============================================================================

@mcp.tool(name="check_batch", title="Check Batch", description="Check multiple domains/URLs/IPs in one call. Returns list of {value, is_safe, verdict, explanation}.",
          annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
          structured_output=True)
async def check_batch(
    values: Annotated[List[str], Field(description="Domains, URLs or IP addresses to check against the blacklists.")],
) -> Annotated[CallToolResult, List[CheckBatchItem]]:
    """Check multiple values against the blacklist in a single call."""
    try:
        core = get_core()
        results = []
        # One shared connection for the whole batch: each core.check()
        # reuses it instead of paying a connect per value.
        with core.storage.shared_connection():
            for value in values:
                if not validate_input(value):
                    results.append({"value": value, "is_safe": False, "verdict": "invalid", "explanation": "Invalid input format."})
                else:
                    res = core.check(value)
                    results.append({
                        "value": value,
                        "is_safe": not res.blacklisted,
                        "verdict": "blacklisted" if res.blacklisted else "safe",
                        "explanation": res.explanation,
                    })
        return results
    except MCPError:
        # Protocol-level errors must keep raising so they surface as JSON-RPC
        # errors rather than tool results.
        raise
    except Exception as exc:
        return _error_result(exc)


@mcp.tool(name="get_status", title="Get Status", description="Get blacklist status including entry counts and sources. Returns JSON: {entry_count, last_update, sources, server_status, source_counts, scheduler_alive}.",
          annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
          structured_output=True)
async def get_status() -> Annotated[CallToolResult, GetStatusResult]:
    """Return current blacklist status, including per-source entry counts."""
    try:
        core = get_core()
        status = core.get_status()
        source_counts = core.storage.get_source_counts()
        return {
            "entry_count": status.entry_count,
            "last_update": status.last_update,
            "sources": status.sources,
            "server_status": status.server_status,
            "source_counts": source_counts,
            "scheduler_alive": core.scheduler_alive()
        }
    except MCPError:
        raise
    except Exception as exc:
        return _error_result(exc)


@mcp.tool(title="Update Blacklists", description="Force immediate update of all blacklists. Rate limited to one update per min_update_interval_seconds. Returns JSON: {updated: bool, reason?: str}.",
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True),
          structured_output=True)
async def update_blacklists(ctx: Context) -> Annotated[CallToolResult, UpdateBlacklistsResult]:
    """Trigger an immediate blacklist refresh.

    Reports one ``notifications/progress`` per source when the caller supplied
    a progress token; refused calls return ``{"updated": False, "reason": ...}``
    without starting any download.
    """
    try:
        core = get_core()
        updater = core.updater

        def _on_source(source: str, index: int, count: int) -> None:
            # Bridge back onto the server loop: the update runs inside
            # anyio.to_thread's worker, so hop with anyio.from_thread.run.
            # report_progress is a no-op when the caller sent no token.
            try:
                anyio.from_thread.run(
                    ctx.report_progress, index, count, f"Updating {source}"
                )
            except RuntimeError:
                # Not on an anyio worker thread (e.g. a scheduled update firing
                # while the callback is installed) — progress is best effort.
                pass

        updater.progress_callback = _on_source
        try:
            # Offload to thread to avoid nested event loops
            result = await anyio.to_thread.run_sync(core.update)
        finally:
            # Only clear our own callback — a concurrent call's must survive.
            if updater.progress_callback is _on_source:
                updater.progress_callback = None
        # core.update() returns the updater's ack; a monkeypatched or legacy
        # None return still means the update ran.
        return result or {"updated": True}
    except MCPError:
        raise
    except Exception as exc:
        return _error_result(exc)


# ============================================================================
# DIAGNOSTICS - Consolidated monitoring and debugging
# ============================================================================

@mcp.tool(name="get_diagnostics", title="Get Diagnostics", description="Get diagnostic information. Mode options: 'summary' (default), 'full', 'health', 'performance', 'sample'.",
          annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
          structured_output=True)
async def get_diagnostics(
    mode: Annotated[
        Literal["summary", "full", "health", "performance", "sample"],
        Field(description="Diagnostic mode: 'summary' (default), 'full', 'health', 'performance' or 'sample'."),
    ] = "summary",
    sample_count: Annotated[
        int,
        Field(ge=1, le=100, description="Number of entries to return in 'sample' mode (1-100)."),
    ] = 10,
) -> Annotated[CallToolResult, GetDiagnosticsResult]:
    """
    Get diagnostic information about the blacklist system.

    Modes:
    - summary: Entry counts, sources, last update (default)
    - full: All available diagnostic data
    - health: Database and scheduler health status
    - performance: Performance metrics and hit rates (v2 only)
    - sample: Random sample of blacklist entries
    """
    try:
        core = get_core()

        if mode == "health":
            # Health check
            db_ok = True
            try:
                core.storage.count_entries()
            except Exception:
                db_ok = False
            scheduler_alive = core.scheduler_alive()
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
                    "scheduler_alive": core.scheduler_alive()
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
    except MCPError:
        raise
    except Exception as exc:
        return _error_result(exc)


# ============================================================================
# ADMINISTRATIVE - Manual entry management
# ============================================================================

_MANUAL_SOURCE = "manual"


@mcp.tool(name="add_entry", title="Add Entry", description="Add a manual blacklist entry.",
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
          structured_output=True)
async def add_entry(
    url: Annotated[Optional[str], Field(description="URL or domain to blacklist (scheme added if missing).")] = None,
    ip: Annotated[Optional[str], Field(description="IPv4 or IPv6 address to blacklist.")] = None,
    date: Annotated[Optional[str], Field(description="Entry timestamp; defaults to the current time.")] = None,
    score: Annotated[float, Field(ge=0, le=10, description="Threat score between 0 and 10.")] = 8.0,
    source: Annotated[str, Field(description="Entry source label; always stored as 'manual'.")] = _MANUAL_SOURCE,
) -> Annotated[CallToolResult, AddEntryResult]:
    """Add a manual blacklist entry."""
    try:
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
    except MCPError:
        raise
    except Exception as exc:
        return _error_result(exc)


@mcp.tool(name="remove_entry", title="Remove Entry", description="Remove a blacklist entry by URL or IP.",
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
          structured_output=True)
async def remove_entry(
    value: Annotated[str, Field(description="Domain, URL or IP address to remove from the blacklist.")],
) -> Annotated[CallToolResult, RemoveEntryResult]:
    """Remove a blacklist entry by URL or IP."""
    try:
        success = get_core().storage.remove_entry(value)
        return {"success": success}
    except MCPError:
        raise
    except Exception as exc:
        return _error_result(exc)
