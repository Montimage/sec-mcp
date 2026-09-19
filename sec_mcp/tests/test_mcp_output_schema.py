"""Structured output and error-semantics tests (issue #36).

Exercises the real MCPServer through an in-memory client session and asserts
the MCP spec 2025-06-18+ structured-output contract:

- ``tools/list`` exposes an ``outputSchema`` for all six tools, derived from
  typed pydantic return models.
- Call results carry ``structuredContent`` plus the serialized text
  ``content`` old clients already consume.
- ``check_batch`` items report a tri-state ``verdict``
  (``safe`` / ``blacklisted`` / ``invalid``).
- Domain failures surface as ``isError: true`` results — never as
  connection-killing exceptions.
"""

import json

import pytest
from mcp.client import Client

from sec_mcp import mcp_server
from sec_mcp.storage import Storage
from sec_mcp.storage_v2 import HybridStorage

EXPECTED_TOOL_NAMES = {
    "check_batch",
    "get_status",
    "update_blacklists",
    "get_diagnostics",
    "add_entry",
    "remove_entry",
}


@pytest.fixture(params=["v1", "v2"], ids=["storage-v1", "storage-v2"])
def backend_storage(request, tmp_path, monkeypatch):
    """Swap the server's storage for each backend (v1 Storage, v2 HybridStorage)."""
    cls = Storage if request.param == "v1" else HybridStorage
    s = cls(str(tmp_path / f"backend-{request.param}.db"))
    monkeypatch.setattr(mcp_server.core, "storage", s)
    return s


def _client_session():
    """In-memory MCP client wired to the real MCPServer (see test_mcp_server)."""
    return Client(mcp_server.mcp, mode="legacy")


def _wire(tool):
    """Serialize a listed tool the way ``tools/list`` puts it on the wire."""
    return tool.model_dump(by_alias=True, exclude_none=True)


def _text_payload(result):
    """The serialized text channel: every content block's text joined."""
    assert result.content, "expected at least one content block"
    assert all(block.type == "text" for block in result.content)
    return "".join(block.text for block in result.content)


# ============================================================================
# outputSchema — typed return models on tools/list
# ============================================================================


@pytest.mark.asyncio
async def test_output_schema_published_for_all_six_tools():
    """Every tool declares a typed return model -> outputSchema on tools/list."""
    async with _client_session() as session:
        listed = await session.list_tools()

    tools = {t.name: t for t in listed.tools}
    assert set(tools) == EXPECTED_TOOL_NAMES
    for name, tool in tools.items():
        schema = tool.output_schema
        assert schema is not None, f"{name}: missing outputSchema"
        assert schema.get("type") == "object", f"{name}: schema not an object"
        assert schema.get("properties"), f"{name}: schema has no properties"


@pytest.mark.asyncio
async def test_output_schema_check_batch_verdict_is_tri_state():
    """check_batch items declare the tri-state verdict enum."""
    async with _client_session() as session:
        listed = await session.list_tools()

    schema = next(t for t in listed.tools if t.name == "check_batch").output_schema
    item_schema = schema["properties"]["result"]["items"]
    if "$ref" in item_schema:  # pydantic emits item models under $defs
        item_schema = schema["$defs"][item_schema["$ref"].rsplit("/", 1)[-1]]
    verdict = item_schema["properties"]["verdict"]
    assert set(verdict["enum"]) == {"safe", "blacklisted", "invalid"}
    assert {"value", "is_safe", "verdict", "explanation"} <= set(
        item_schema["properties"]
    )


# ============================================================================
# structuredContent + serialized text on every call result
# ============================================================================


@pytest.mark.asyncio
async def test_output_schema_results_carry_structured_content_and_text(backend_storage):
    """Successful calls return structuredContent AND the legacy text content."""
    async with _client_session() as session:
        calls = [
            ("check_batch", {"values": ["example.com"]}),
            ("get_status", {}),
            ("get_diagnostics", {"mode": "summary"}),
            ("add_entry", {"url": "evil.example"}),
            ("remove_entry", {"value": "evil.example"}),
        ]
        for name, args in calls:
            result = await session.call_tool(name, args)
            assert result.is_error is False, name
            # Back-compat: the serialized text channel still carries JSON.
            assert json.loads(_text_payload(result)) is not None, name
            # New channel: structured content matching the declared schema.
            assert result.structured_content is not None, name


@pytest.mark.asyncio
async def test_output_schema_update_blacklists_structured_content(backend_storage, monkeypatch):
    # Characterize the tool contract, not the updater: a real update downloads feeds.
    monkeypatch.setattr(mcp_server.core, "update", lambda: None)
    async with _client_session() as session:
        result = await session.call_tool("update_blacklists", {})

    assert result.is_error is False
    assert result.structured_content == {"updated": True}
    assert json.loads(_text_payload(result)) == {"updated": True}


@pytest.mark.asyncio
async def test_output_schema_get_status_structured_content(backend_storage):
    async with _client_session() as session:
        result = await session.call_tool("get_status", {})

    assert result.is_error is False
    structured = result.structured_content
    assert isinstance(structured["entry_count"], int)
    assert isinstance(structured["source_counts"], dict)
    assert structured["server_status"]


# ============================================================================
# check_batch tri-state verdict
# ============================================================================


@pytest.mark.asyncio
async def test_output_schema_check_batch_verdict_tri_state(backend_storage):
    """safe, blacklisted and invalid values each get the matching verdict."""
    async with _client_session() as session:
        added = await session.call_tool("add_entry", {"url": "evil.example"})
        assert added.is_error is False
        result = await session.call_tool(
            "check_batch",
            {"values": ["example.com", "evil.example", "not a domain"]},
        )

    assert result.is_error is False
    items = result.structured_content["result"]
    verdicts = {item["value"]: item["verdict"] for item in items}
    assert verdicts == {
        "example.com": "safe",
        "evil.example": "blacklisted",
        "not a domain": "invalid",
    }
    # The serialized text channel reports the same verdicts.
    text_items = [json.loads(b.text) for b in result.content]
    assert {i["value"]: i["verdict"] for i in text_items} == verdicts


# ============================================================================
# isError — domain failures become error results, never crashes
# ============================================================================


@pytest.mark.asyncio
async def test_is_error_on_add_entry_validation_failures(backend_storage):
    """Invalid add_entry input surfaces as isError, not a raised exception."""
    async with _client_session() as session:
        for args in (
            {},
            {"url": "%%% not a url %%%"},
            {"url": "http://localhost"},
            {"ip": "999.999.999.999"},
            {"url": "evil.example", "score": 11},
        ):
            result = await session.call_tool("add_entry", args)
            assert result.is_error is True, args
            assert _text_payload(result), args
            # Error results carry text content, not structured content.
            assert result.structured_content is None, args


@pytest.mark.asyncio
async def test_is_error_on_argument_schema_violation():
    """Input-schema violations also surface as isError results on the wire."""
    async with _client_session() as session:
        result = await session.call_tool("check_batch", {"values": "not-a-list"})

    assert result.is_error is True


@pytest.mark.asyncio
async def test_is_error_on_domain_failure_and_session_survives(backend_storage):
    """A crashing backend returns isError; the connection keeps working."""
    core = mcp_server.core
    real = core.storage
    core.storage = None
    try:
        async with _client_session() as session:
            failed = await session.call_tool("get_status", {})
            assert failed.is_error is True
            assert _text_payload(failed)

            # The backend recovers and the same session keeps serving tools.
            core.storage = real
            ok = await session.call_tool("get_status", {})
            assert ok.is_error is False
            assert ok.structured_content is not None
    finally:
        core.storage = real
