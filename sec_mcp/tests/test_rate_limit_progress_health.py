"""Rate limiting, progress notifications and honest health (issue #38).

- ``update_blacklists`` refuses a second call inside ``min_update_interval``
  with ``{"updated": False, "reason": ...}`` and starts zero downloads.
- When the caller supplies a progress token, ``update_blacklists`` emits at
  least one ``notifications/progress`` per blacklist source.
- ``scheduler_alive`` in ``get_status``/``get_diagnostics`` reports the real
  scheduler thread state instead of a hardcoded ``True``.

All downloads are stubbed — no test touches the network.
"""

import json
import threading
import time

import pytest
from mcp.client import Client

from sec_mcp import mcp_server
from sec_mcp.storage import Storage
from sec_mcp.update_blacklist import BlacklistUpdater


def _client_session():
    """In-memory MCP client wired to the real MCPServer (see test_mcp_server)."""
    return Client(mcp_server.mcp, mode="legacy")


def _json_blocks(result):
    """Parse every text content block of a CallToolResult as JSON."""
    assert result.content, "expected at least one content block"
    return [json.loads(block.text) for block in result.content]


def _new_updater(tmp_path, monkeypatch, sources=None, min_interval=300):
    """A fresh BlacklistUpdater backed by tmp storage and tmp config."""
    config = tmp_path / "sources.json"
    config.write_text(json.dumps({
        "blacklist_sources": sources or {
            "FeedA": "https://feed.example/a.txt",
            "FeedB": "https://feed.example/b.txt",
        },
        "min_update_interval_seconds": min_interval,
    }))
    storage = Storage(str(tmp_path / "feed.db"))
    return BlacklistUpdater(storage, config_path=str(config))


def _counting_stub(calls):
    """An async ``_update_source`` replacement that only counts invocations."""

    async def stub(client, source, url):
        calls.append(source)

    return stub


# ============================================================================
# Rate limiting — second update_blacklists inside the minimum interval
# ============================================================================


def test_rate_limit_second_force_update_refused_without_downloads(tmp_path, monkeypatch):
    """A second force_update inside the interval refuses and downloads nothing."""
    updater = _new_updater(tmp_path, monkeypatch, min_interval=300)
    calls = []
    monkeypatch.setattr(updater, "_update_source", _counting_stub(calls))

    first = updater.force_update()
    assert first == {"updated": True}
    assert sorted(calls) == ["FeedA", "FeedB"]

    second = updater.force_update()
    assert second["updated"] is False
    assert isinstance(second["reason"], str) and second["reason"]
    # Zero downloads were started by the refused call.
    assert sorted(calls) == ["FeedA", "FeedB"]


def test_rate_limit_allows_update_after_interval(tmp_path, monkeypatch):
    """Once the interval has elapsed, a forced update runs again."""
    updater = _new_updater(tmp_path, monkeypatch, min_interval=60)
    updater._last_force_update = time.monotonic() - 61
    calls = []
    monkeypatch.setattr(updater, "_update_source", _counting_stub(calls))

    assert updater.force_update() == {"updated": True}
    assert len(calls) == 2


def test_rate_limit_zero_interval_disables(tmp_path, monkeypatch):
    """min_update_interval_seconds: 0 keeps forced updates always allowed."""
    updater = _new_updater(tmp_path, monkeypatch, min_interval=0)
    calls = []
    monkeypatch.setattr(updater, "_update_source", _counting_stub(calls))

    assert updater.force_update() == {"updated": True}
    assert updater.force_update() == {"updated": True}
    assert len(calls) == 4


@pytest.fixture
def server_updater(tmp_path, monkeypatch):
    """The shared server's updater with stubbed downloads and clean rate state."""
    core = mcp_server.core
    monkeypatch.setattr(core.updater, "_last_force_update", None)
    monkeypatch.setattr(core.updater, "progress_callback", None)
    calls = []
    monkeypatch.setattr(core.updater, "_update_source", _counting_stub(calls))
    yield core.updater, calls
    monkeypatch.setattr(core.updater, "_last_force_update", None)


@pytest.mark.asyncio
async def test_rate_limit_update_blacklists_tool_returns_reason(server_updater):
    """The tool surfaces {updated: false, reason} and starts no downloads."""
    updater, calls = server_updater
    async with _client_session() as session:
        first = await session.call_tool("update_blacklists", {})
        assert first.is_error is False
        (payload,) = _json_blocks(first)
        assert payload == {"updated": True}
        assert len(calls) == len(updater.sources)

        calls.clear()
        second = await session.call_tool("update_blacklists", {})

    assert second.is_error is False
    (payload,) = _json_blocks(second)
    assert payload["updated"] is False
    assert isinstance(payload["reason"], str) and payload["reason"]
    # The refused call started zero downloads.
    assert calls == []
    # structuredContent carries the refusal too (extra="allow" passes reason).
    assert second.structured_content["updated"] is False
    assert second.structured_content["reason"] == payload["reason"]


# ============================================================================
# Progress notifications — >= 1 notifications/progress per source
# ============================================================================


@pytest.mark.asyncio
async def test_progress_notification_per_source_with_token(server_updater):
    """A progress token yields one notifications/progress per source."""
    updater, calls = server_updater
    progress = []

    async def on_progress(value, total, message):
        progress.append((value, total, message))

    async with _client_session() as session:
        result = await session.call_tool(
            "update_blacklists", {}, progress_callback=on_progress
        )

    assert result.is_error is False
    n_sources = len(updater.sources)
    assert len(progress) >= n_sources
    assert len(calls) == n_sources
    # One report per source, counted 1..N against the same total.
    assert [value for value, _, _ in progress[:n_sources]] == list(
        range(1, n_sources + 1)
    )
    assert all(total == n_sources for _, total, _ in progress[:n_sources])
    for source in updater.sources:
        assert any(source in (message or "") for _, _, message in progress)


@pytest.mark.asyncio
async def test_progress_update_without_token_still_succeeds(server_updater):
    """No progress token: the update still runs and the callback is cleared."""
    updater, calls = server_updater
    async with _client_session() as session:
        result = await session.call_tool("update_blacklists", {})

    assert result.is_error is False
    assert len(calls) == len(updater.sources)
    assert updater.progress_callback is None


# ============================================================================
# Honest health — scheduler_alive mirrors the real thread state
# ============================================================================


def _dead_thread():
    thread = threading.Thread(target=lambda: None, daemon=True)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    return thread


@pytest.mark.asyncio
async def test_health_reports_false_when_scheduler_thread_dead(monkeypatch):
    """A dead scheduler thread must report scheduler_alive: false."""
    monkeypatch.setattr(BlacklistUpdater, "_scheduler_thread", _dead_thread())

    result = await mcp_server.get_diagnostics(mode="health")
    assert result["scheduler_alive"] is False

    result = await mcp_server.get_diagnostics(mode="full")
    assert result["health"]["scheduler_alive"] is False


@pytest.mark.asyncio
async def test_health_reports_false_when_scheduler_never_started(monkeypatch):
    """Scheduler disabled (no thread) reports scheduler_alive: false."""
    monkeypatch.setattr(BlacklistUpdater, "_scheduler_thread", None)

    result = await mcp_server.get_diagnostics(mode="health")
    assert result["scheduler_alive"] is False


@pytest.mark.asyncio
async def test_health_reports_true_while_scheduler_thread_runs(monkeypatch):
    """A live scheduler thread reports scheduler_alive: true."""
    stop = threading.Event()
    thread = threading.Thread(target=stop.wait, daemon=True)
    thread.start()
    monkeypatch.setattr(BlacklistUpdater, "_scheduler_thread", thread)
    try:
        result = await mcp_server.get_diagnostics(mode="health")
        assert result["scheduler_alive"] is True

        result = await mcp_server.get_diagnostics(mode="full")
        assert result["health"]["scheduler_alive"] is True
    finally:
        stop.set()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_health_get_status_reports_real_scheduler_state(monkeypatch):
    """get_status carries the same honest scheduler_alive flag."""
    monkeypatch.setattr(BlacklistUpdater, "_scheduler_thread", _dead_thread())
    status = await mcp_server.get_status()
    assert status["scheduler_alive"] is False

    stop = threading.Event()
    thread = threading.Thread(target=stop.wait, daemon=True)
    thread.start()
    monkeypatch.setattr(BlacklistUpdater, "_scheduler_thread", thread)
    try:
        status = await mcp_server.get_status()
        assert status["scheduler_alive"] is True
    finally:
        stop.set()
        thread.join(timeout=5)
