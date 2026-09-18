"""Unit tests for the MCP admin tools' input validation."""

import sqlite3

import pytest

from sec_mcp import mcp_server
from sec_mcp.storage import Storage
from sec_mcp.storage_v2 import HybridStorage


@pytest.fixture
def storage(tmp_path, monkeypatch):
    s = Storage(str(tmp_path / "admin.db"))
    monkeypatch.setattr(mcp_server.core, "storage", s)
    return s


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
    # "http://localhost" passes the URL pattern but its host can never be
    # stored as a domain entry — reject instead of reporting false success.
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
