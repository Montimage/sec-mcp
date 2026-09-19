"""tools/list annotation contract tests (issue #35).

Exercises the real MCPServer through an in-memory client session and asserts
the MCP tool annotations surfaced by ``tools/list``: safety hints
(``readOnlyHint``/``destructiveHint``/``idempotentHint``/``openWorldHint``) and
a human-readable ``title`` on every tool.
"""

import pytest
from mcp.client import Client

from sec_mcp import mcp_server

EXPECTED_TOOL_NAMES = {
    "check_batch",
    "get_status",
    "update_blacklists",
    "get_diagnostics",
    "add_entry",
    "remove_entry",
}

READ_ONLY_TOOLS = {"check_batch", "get_status", "get_diagnostics"}


def _client_session():
    """In-memory MCP client wired to the real MCPServer (see test_mcp_server)."""
    return Client(mcp_server.mcp, mode="legacy")


def _wire(tool):
    """Serialize a listed tool the way ``tools/list`` puts it on the wire."""
    return tool.model_dump(by_alias=True, exclude_none=True)


@pytest.mark.asyncio
async def test_tool_annotations_read_only_hint():
    """check_batch, get_status and get_diagnostics are marked read-only."""
    async with _client_session() as session:
        listed = await session.list_tools()

    tools = {t.name: _wire(t) for t in listed.tools}
    assert set(tools) == EXPECTED_TOOL_NAMES
    for name in READ_ONLY_TOOLS:
        assert tools[name]["annotations"]["readOnlyHint"] is True, name
    for name in EXPECTED_TOOL_NAMES - READ_ONLY_TOOLS:
        assert tools[name]["annotations"]["readOnlyHint"] is False, name


@pytest.mark.asyncio
async def test_tool_annotations_remove_entry_destructive():
    """remove_entry is the only tool marked destructive."""
    async with _client_session() as session:
        listed = await session.list_tools()

    tools = {t.name: _wire(t) for t in listed.tools}
    assert tools["remove_entry"]["annotations"]["destructiveHint"] is True
    for name in EXPECTED_TOOL_NAMES - {"remove_entry"}:
        assert tools[name]["annotations"]["destructiveHint"] is False, name


@pytest.mark.asyncio
async def test_tool_annotations_add_entry_idempotent_not_destructive():
    """add_entry is non-destructive and idempotent."""
    async with _client_session() as session:
        listed = await session.list_tools()

    annotations = _wire(next(t for t in listed.tools if t.name == "add_entry"))[
        "annotations"
    ]
    assert annotations["destructiveHint"] is False
    assert annotations["idempotentHint"] is True


@pytest.mark.asyncio
async def test_tool_annotations_open_world_only_on_update_blacklists():
    """openWorldHint is true on update_blacklists and nowhere else."""
    async with _client_session() as session:
        listed = await session.list_tools()

    tools = {t.name: _wire(t) for t in listed.tools}
    assert tools["update_blacklists"]["annotations"]["openWorldHint"] is True
    for name in EXPECTED_TOOL_NAMES - {"update_blacklists"}:
        assert tools[name]["annotations"].get("openWorldHint") is not True, name


@pytest.mark.asyncio
async def test_tool_annotations_every_tool_has_title():
    """Every tool exposes a non-empty human-readable title."""
    async with _client_session() as session:
        listed = await session.list_tools()

    assert {t.name for t in listed.tools} == EXPECTED_TOOL_NAMES
    for tool in listed.tools:
        assert _wire(tool)["title"], tool.name
