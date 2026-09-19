"""Unit tests for the MCP admin tools' input validation.

Also carries the characterization suite: every registered MCP tool is
exercised through an in-memory client session on both storage backends
(v1 ``Storage`` and v2 ``HybridStorage``), asserting tool names, argument
schemas and result shapes — the safety net for the SDK major upgrade.
"""

import json
import sqlite3
import sys

import pytest
from mcp import StdioServerParameters
from mcp.client import Client

from sec_mcp import mcp_server
from sec_mcp.storage import Storage
from sec_mcp.storage_v2 import HybridStorage

# Expected tool catalog: name -> (required args, all argument-schema properties).
EXPECTED_TOOLS = {
    "check_batch": (["values"], {"values"}),
    "get_status": ([], set()),
    "update_blacklists": ([], set()),
    "get_diagnostics": ([], {"mode", "sample_count"}),
    "add_entry": ([], {"url", "ip", "date", "score", "source"}),
    "remove_entry": (["value"], {"value"}),
}


@pytest.fixture
def storage(tmp_path, monkeypatch):
    s = Storage(str(tmp_path / "admin.db"))
    monkeypatch.setattr(mcp_server.core, "storage", s)
    return s


@pytest.fixture(params=["v1", "v2"], ids=["storage-v1", "storage-v2"])
def backend_storage(request, tmp_path, monkeypatch):
    """Swap the server's storage for each backend (v1 Storage, v2 HybridStorage)."""
    cls = Storage if request.param == "v1" else HybridStorage
    s = cls(str(tmp_path / f"backend-{request.param}.db"))
    monkeypatch.setattr(mcp_server.core, "storage", s)
    return s


def _client_session():
    """In-memory MCP client wired to the real MCPServer.

    SDK v2 removed ``create_connected_server_and_client_session``; ``Client``
    accepts an ``MCPServer`` directly. ``mode="legacy"`` keeps the v1-style
    in-memory JSON-RPC transport plus the initialize handshake.
    """
    return Client(mcp_server.mcp, mode="legacy")


def _json_blocks(result):
    """Parse every text content block of a CallToolResult as JSON."""
    assert result.content, "expected at least one content block"
    assert all(block.type == "text" for block in result.content)
    return [json.loads(block.text) for block in result.content]


@pytest.mark.asyncio
async def test_add_entry_requires_url_or_ip(storage):
    with pytest.raises(ValueError):
        await mcp_server.add_entry()
    assert storage.count_entries() == 0


@pytest.mark.asyncio
async def test_add_entry_rejects_invalid_url(storage):
    with pytest.raises(ValueError):
        await mcp_server.add_entry(url="%%% not a url %%%")
    assert storage.count_entries() == 0


@pytest.mark.asyncio
async def test_add_entry_rejects_unusable_url_host(storage):
    with pytest.raises(ValueError):
        await mcp_server.add_entry(url="http://localhost")
    assert storage.count_entries() == 0


@pytest.mark.asyncio
async def test_add_entry_rejects_invalid_ip(storage):
    with pytest.raises(ValueError):
        await mcp_server.add_entry(ip="999.999.999.999")
    assert storage.count_entries() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_score", [-1, 10.5, float("nan"), float("inf"), "high", True])
async def test_add_entry_rejects_invalid_score(storage, bad_score):
    with pytest.raises(ValueError):
        await mcp_server.add_entry(url="evil.com", score=bad_score)
    assert storage.count_entries() == 0


@pytest.mark.asyncio
async def test_add_entry_ignores_caller_source(storage):
    await mcp_server.add_entry(url="evil.com", source="attacker-controlled")
    with sqlite3.connect(storage.db_path) as conn:
        row = conn.execute(
            "SELECT source FROM blacklist_domain WHERE domain = ?", ("evil.com",)
        ).fetchone()
    assert row[0] == "manual"


@pytest.mark.asyncio
async def test_add_entry_accepts_valid_url_and_ip(storage):
    await mcp_server.add_entry(url="evil.com", ip="9.9.9.9", score=9.5)
    assert storage.is_domain_blacklisted("evil.com")
    assert storage.is_ip_blacklisted("9.9.9.9")


@pytest.mark.asyncio
async def test_add_entry_accepts_score_boundaries(storage):
    await mcp_server.add_entry(url="zero-score.com", score=0)
    await mcp_server.add_entry(url="ten-score.com", score=10)
    assert storage.is_domain_blacklisted("zero-score.com")
    assert storage.is_domain_blacklisted("ten-score.com")


@pytest.mark.asyncio
async def test_add_entry_url_with_path(storage):
    await mcp_server.add_entry(url="https://evil.example/phish")
    assert storage.is_url_blacklisted("https://evil.example/phish")


@pytest.mark.asyncio
async def test_add_entry_works_with_v2_storage(tmp_path, monkeypatch):
    s = HybridStorage(str(tmp_path / "admin-v2.db"))
    monkeypatch.setattr(mcp_server.core, "storage", s)
    await mcp_server.add_entry(url="evil.com", ip="9.9.9.9")
    assert s.is_domain_blacklisted("evil.com")
    assert s.is_ip_blacklisted("9.9.9.9")


@pytest.mark.asyncio
async def test_remove_entry_domain_flips_lookup(storage):
    await mcp_server.add_entry(url="evil.com")
    assert storage.is_domain_blacklisted("evil.com")
    result = await mcp_server.remove_entry("evil.com")
    assert result["success"] is True
    assert not storage.is_domain_blacklisted("evil.com")


@pytest.mark.asyncio
async def test_remove_entry_url_flips_lookup(storage):
    await mcp_server.add_entry(url="https://evil.example/phish")
    assert storage.is_url_blacklisted("https://evil.example/phish")
    result = await mcp_server.remove_entry("https://evil.example/phish")
    assert result["success"] is True
    assert not storage.is_url_blacklisted("https://evil.example/phish")


@pytest.mark.asyncio
async def test_remove_entry_ip_flips_lookup(storage):
    await mcp_server.add_entry(ip="9.9.9.9")
    assert storage.is_ip_blacklisted("9.9.9.9")
    result = await mcp_server.remove_entry("9.9.9.9")
    assert result["success"] is True
    assert not storage.is_ip_blacklisted("9.9.9.9")


@pytest.mark.asyncio
async def test_remove_entry_unknown_returns_false(storage):
    result = await mcp_server.remove_entry("not-present.example")
    assert result["success"] is False


# ============================================================================
# Characterization tests — in-memory client over both storage backends
# ============================================================================


@pytest.mark.asyncio
async def test_tool_catalog_names_and_argument_schemas(backend_storage):
    """All six tools are registered with the expected names and input schemas."""
    async with _client_session() as session:
        listed = await session.list_tools()

    tools = {t.name: t for t in listed.tools}
    assert set(tools) == set(EXPECTED_TOOLS)
    for name, (required, properties) in EXPECTED_TOOLS.items():
        schema = tools[name].input_schema
        assert schema.get("type") == "object", name
        assert set(schema.get("properties", {})) == properties, name
        assert sorted(schema.get("required") or []) == required, name


@pytest.mark.asyncio
async def test_call_check_batch_result_shape(backend_storage):
    async with _client_session() as session:
        result = await session.call_tool(
            "check_batch", {"values": ["example.com", "9.9.9.9"]}
        )

    assert result.is_error is False
    items = _json_blocks(result)
    assert [item["value"] for item in items] == ["example.com", "9.9.9.9"]
    for item in items:
        assert set(item) == {"value", "is_safe", "explanation"}
        assert item["is_safe"] is True
        assert isinstance(item["explanation"], str)


@pytest.mark.asyncio
async def test_call_get_status_result_shape(backend_storage):
    async with _client_session() as session:
        result = await session.call_tool("get_status", {})

    assert result.is_error is False
    (payload,) = _json_blocks(result)
    assert {
        "entry_count",
        "last_update",
        "sources",
        "server_status",
        "source_counts",
    } <= set(payload)
    assert isinstance(payload["entry_count"], int)
    assert isinstance(payload["source_counts"], dict)


@pytest.mark.asyncio
async def test_call_update_blacklists_result_shape(backend_storage, monkeypatch):
    # Characterize the tool contract, not the updater: a real update downloads feeds.
    monkeypatch.setattr(mcp_server.core, "update", lambda: None)
    async with _client_session() as session:
        result = await session.call_tool("update_blacklists", {})

    assert result.is_error is False
    (payload,) = _json_blocks(result)
    assert payload == {"updated": True}


@pytest.mark.asyncio
async def test_call_get_diagnostics_summary_result_shape(backend_storage):
    async with _client_session() as session:
        result = await session.call_tool("get_diagnostics", {"mode": "summary"})

    assert result.is_error is False
    (payload,) = _json_blocks(result)
    assert payload["mode"] == "summary"
    assert {"total_entries", "per_source", "last_updates"} <= set(payload)
    assert isinstance(payload["total_entries"], int)
    assert isinstance(payload["per_source"], dict)


@pytest.mark.asyncio
async def test_call_add_entry_result_shape(backend_storage):
    async with _client_session() as session:
        result = await session.call_tool(
            "add_entry", {"url": "evil.example", "score": 7.5}
        )

    assert result.is_error is False
    (payload,) = _json_blocks(result)
    assert payload == {"success": True}
    assert backend_storage.is_domain_blacklisted("evil.example")


@pytest.mark.asyncio
async def test_call_remove_entry_result_shape(backend_storage):
    async with _client_session() as session:
        await session.call_tool("add_entry", {"url": "evil.example"})
        result = await session.call_tool("remove_entry", {"value": "evil.example"})

    assert result.is_error is False
    (payload,) = _json_blocks(result)
    assert payload == {"success": True}
    assert not backend_storage.is_domain_blacklisted("evil.example")


# ============================================================================
# Wire-level acceptance tests — real stdio transport (issue #34)
# ============================================================================

# tools/list contract: same six tool names, in registration order.
EXPECTED_TOOL_ORDER = [
    "check_batch",
    "get_status",
    "update_blacklists",
    "get_diagnostics",
    "add_entry",
    "remove_entry",
]

# Versions the legacy initialize handshake can negotiate (all pre-2026).
LEGACY_PROTOCOL_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
}


def _stdio_params() -> StdioServerParameters:
    """Server parameters that spawn the real stdio entry point.

    ``env=None`` inherits this process's environment, so the hermetic
    ``MCP_*`` paths conftest installed are honored by the subprocess too.
    """
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", "from sec_mcp.start_server import main; main()"],
    )


@pytest.mark.asyncio
async def test_stdio_discover_reports_2026_07_28():
    """A server/discover request over stdio lists 2026-07-28 support."""
    async with Client(_stdio_params(), mode="auto") as client:
        # mode="auto" lands on 2026-07-28 only when server/discover answers.
        assert client.protocol_version == "2026-07-28"
        result = client.session.discover_result
        assert result is not None
        assert "2026-07-28" in result.supported_versions


@pytest.mark.asyncio
async def test_stdio_initialize_legacy_handshake():
    """A legacy initialize handshake over stdio still succeeds."""
    async with Client(_stdio_params(), mode="legacy") as client:
        # The initialize handshake completed and negotiated a pre-2026 version.
        assert client.protocol_version in LEGACY_PROTOCOL_VERSIONS
        assert client.session.initialize_result is not None
        tools = await client.list_tools()
        assert [t.name for t in tools.tools] == EXPECTED_TOOL_ORDER


@pytest.mark.asyncio
async def test_stdio_tools_list_order_stable():
    """tools/list returns the same 6 names in identical order across 3 calls."""
    async with Client(_stdio_params(), mode="auto") as client:
        orders = []
        for _ in range(3):
            listed = await client.list_tools()
            orders.append([t.name for t in listed.tools])
    assert orders[0] == orders[1] == orders[2] == EXPECTED_TOOL_ORDER
