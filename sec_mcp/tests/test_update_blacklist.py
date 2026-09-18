import sqlite3
from unittest.mock import ANY, MagicMock

import pytest

from sec_mcp.storage import Storage
from sec_mcp.update_blacklist import BlacklistUpdater, _feed_cache_dir


class _FakeStreamResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def raise_for_status(self):
        pass

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _stream_client(chunks):
    client = MagicMock()
    client.stream = MagicMock(return_value=_FakeStreamCM(_FakeStreamResponse(chunks)))
    return client


def _updater(tmp_path):
    storage = Storage(str(tmp_path / "feed.db"))
    storage.add_domain("keep-me.com", "2025-01-01 00:00:00", 5.0, "seed")
    return storage, BlacklistUpdater(storage)


@pytest.mark.asyncio
async def test_update_source_success(tmp_path):
    storage = MagicMock(spec=Storage)
    updater = BlacklistUpdater(storage)
    content = b"url,ip,date,score\nhttps://malicious.com,1.2.3.4,2025-04-18T00:00:00,9.0\nhttps://phishing.com,2.2.2.2,,\n"
    client = _stream_client([content])
    await updater._update_source(client, "PhishStats", "https://fake-url")

    storage.add_entries.assert_called_once()
    entries = storage.add_entries.call_args[0][0]
    assert ("https://malicious.com", "1.2.3.4", "2025-04-18T00:00:00", 9.0, "PhishStats") in entries
    assert ("https://phishing.com", "2.2.2.2", ANY, 8.0, "PhishStats") in entries


@pytest.mark.asyncio
async def test_update_source_network_error():
    storage = MagicMock(spec=Storage)
    updater = BlacklistUpdater(storage)
    client = MagicMock()
    client.stream = MagicMock(side_effect=Exception("Network error"))
    await updater._update_source(client, "OpenPhish", "https://fake-url")
    assert not storage.add_entries.called


@pytest.mark.asyncio
async def test_feed_rejects_non_https_source(tmp_path):
    storage, updater = _updater(tmp_path)
    client = _stream_client([b"9.9.9.9\n"])
    await updater._update_source(client, "EvilFeed", "http://evil.example/feed")
    client.stream.assert_not_called()
    assert storage.count_entries() == 1


@pytest.mark.asyncio
async def test_feed_oversized_response_keeps_existing(tmp_path):
    storage, updater = _updater(tmp_path)
    updater.max_feed_bytes = 8
    client = _stream_client([b"9.9.9.9\n", b"8.8.8.8\n"])
    await updater._update_source(client, "TestFeed", "https://feed.example/list")
    assert storage.count_entries() == 1
    assert storage.is_domain_blacklisted("keep-me.com")


@pytest.mark.asyncio
async def test_feed_empty_response_keeps_existing(tmp_path):
    storage, updater = _updater(tmp_path)
    client = _stream_client([b"", b"# nothing here\n"])
    await updater._update_source(client, "TestFeed", "https://feed.example/list")
    assert storage.count_entries() == 1
    assert storage.is_domain_blacklisted("keep-me.com")
    assert not (tmp_path / "downloads" / "TestFeed.txt").exists()


@pytest.mark.asyncio
async def test_feed_rejects_invalid_config_limits(tmp_path):
    storage = Storage(str(tmp_path / "feed.db"))
    bad_config = tmp_path / "bad.json"
    bad_config.write_text(
        '{"blacklist_sources": {}, "max_feed_bytes": "bogus", '
        '"min_feed_entries": -3, "max_feed_entries": -1}'
    )
    updater = BlacklistUpdater(storage, config_path=str(bad_config))
    assert updater.max_feed_bytes == 64 * 1024 * 1024
    assert updater.min_feed_entries == 0
    assert updater.max_feed_entries >= updater.min_feed_entries


@pytest.mark.asyncio
async def test_feed_too_few_entries_keeps_existing(tmp_path):
    storage, updater = _updater(tmp_path)
    updater.min_feed_entries = 5
    client = _stream_client([b"9.9.9.9\n8.8.8.8\n"])
    await updater._update_source(client, "TestFeed", "https://feed.example/list")
    assert storage.count_entries() == 1


@pytest.mark.asyncio
async def test_feed_too_many_entries_keeps_existing(tmp_path):
    storage, updater = _updater(tmp_path)
    updater.max_feed_entries = 1
    client = _stream_client([b"9.9.9.9\n8.8.8.8\n"])
    await updater._update_source(client, "TestFeed", "https://feed.example/list")
    assert storage.count_entries() == 1


@pytest.mark.asyncio
async def test_feed_download_failure_keeps_existing(tmp_path):
    storage, updater = _updater(tmp_path)
    client = MagicMock()
    client.stream = MagicMock(side_effect=Exception("connection reset"))
    await updater._update_source(client, "TestFeed", "https://feed.example/list")
    assert storage.count_entries() == 1
    assert storage.is_domain_blacklisted("keep-me.com")


@pytest.mark.asyncio
async def test_feed_atomic_rollback_no_partial_update(tmp_path):
    storage, updater = _updater(tmp_path)
    with sqlite3.connect(storage.db_path) as conn:
        conn.execute("DROP TABLE blacklist_ip")
    client = _stream_client([b"new-bad.com\n9.9.9.9\n"])
    await updater._update_source(client, "TestFeed", "https://feed.example/list")
    with sqlite3.connect(storage.db_path) as conn:
        domain_rows = conn.execute("SELECT COUNT(*) FROM blacklist_domain").fetchone()[0]
    assert domain_rows == 1


@pytest.mark.asyncio
async def test_feed_success_updates_atomically(tmp_path):
    storage, updater = _updater(tmp_path)
    client = _stream_client([b"new-bad.com\n9.9.9.9\nhttps://evil.example/path\n"])
    await updater._update_source(client, "TestFeed", "https://feed.example/list")
    assert storage.is_domain_blacklisted("new-bad.com")
    assert storage.is_ip_blacklisted("9.9.9.9")
    assert storage.is_url_blacklisted("https://evil.example/path")
    assert storage.count_entries() == 4
    assert (tmp_path / "downloads" / "TestFeed.txt").exists()

    # Fresh cache is reused: a failing network on the next call keeps data.
    failing = MagicMock()
    failing.stream = MagicMock(side_effect=Exception("network down"))
    await updater._update_source(failing, "TestFeed", "https://feed.example/list")
    assert storage.count_entries() == 4


def test_feed_cache_dir_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "custom"))
    assert _feed_cache_dir() == str(tmp_path / "custom")


def test_feed_cache_dir_platformdirs_default(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        "sec_mcp.update_blacklist.user_cache_dir", lambda *a, **kw: str(tmp_path / "plat"))
    assert _feed_cache_dir() == str(tmp_path / "plat")


@pytest.mark.asyncio
async def test_update_source_reads_feed_cache_dir(tmp_path, monkeypatch):
    cache_dir = tmp_path / "feed_cache"
    monkeypatch.setenv("MCP_CACHE_DIR", str(cache_dir))
    cache_dir.mkdir()
    (cache_dir / "CINSSCORE.txt").write_text("9.9.9.9\n")
    storage = Storage(str(tmp_path / "feed.db"))
    updater = BlacklistUpdater(storage)
    await updater._update_source(None, "CINSSCORE", "https://feed.example/list.txt")
    assert storage.is_ip_blacklisted("9.9.9.9")
    assert not (tmp_path / "downloads").exists()


@pytest.mark.asyncio
async def test_feed_cache_filename_confined_to_cache_dir(tmp_path, monkeypatch):
    cache_dir = tmp_path / "feed_cache"
    monkeypatch.setenv("MCP_CACHE_DIR", str(cache_dir))
    storage = Storage(str(tmp_path / "feed.db"))
    updater = BlacklistUpdater(storage)
    client = _stream_client([b"9.9.9.9\n"])
    await updater._update_source(client, "../evil", "https://feed.example/list.txt")
    written = list(cache_dir.iterdir())
    assert len(written) == 1
    assert written[0].name == ".._evil.txt"
    assert written[0].parent == cache_dir
    assert not (tmp_path / "evil.txt").exists()


def _dshield_updater(tmp_path, monkeypatch, feed_text):
    cache_dir = tmp_path / "feed_cache"
    monkeypatch.setenv("MCP_CACHE_DIR", str(cache_dir))
    cache_dir.mkdir()
    (cache_dir / "Dshield.txt").write_text(feed_text)
    storage = Storage(str(tmp_path / "feed.db"))
    return storage, BlacklistUpdater(storage)


@pytest.mark.asyncio
async def test_dshield_last_address_of_block_is_blacklisted(tmp_path, monkeypatch):
    storage, updater = _dshield_updater(tmp_path, monkeypatch, (
        "# DShield.org Recommended Block List\n"
        "Start\tEnd\tNetmask\tAttacks\tName\tCountry\temail\n"
        "10.0.0.0\t10.0.0.255\t255.255.255.0\t100\tbad\tXX\tx@y\n"
    ))
    await updater._update_source(None, "Dshield", "https://www.dshield.org/block.txt")
    assert storage.is_ip_blacklisted("10.0.0.255")
    assert storage.is_ip_blacklisted("10.0.0.0")
    assert storage.is_ip_blacklisted("10.0.0.128")
    assert not storage.is_ip_blacklisted("10.0.1.0")


@pytest.mark.asyncio
async def test_dshield_unaligned_range_covers_exact_bounds(tmp_path, monkeypatch):
    storage, updater = _dshield_updater(tmp_path, monkeypatch, (
        "10.0.0.4\t10.0.0.7\t255.255.255.252\t1\tbad\tXX\tx@y\n"
        "10.1.0.5\t10.1.0.5\t255.255.255.255\t1\tbad\tXX\tx@y\n"
    ))
    await updater._update_source(None, "Dshield", "https://www.dshield.org/block.txt")
    assert storage.is_ip_blacklisted("10.0.0.7")
    assert storage.is_ip_blacklisted("10.0.0.5")
    assert not storage.is_ip_blacklisted("10.0.0.3")
    assert not storage.is_ip_blacklisted("10.0.0.8")
    assert storage.is_ip_blacklisted("10.1.0.5")
    assert not storage.is_ip_blacklisted("10.1.0.6")


@pytest.mark.asyncio
async def test_dshield_rejects_malformed_rows(tmp_path, monkeypatch):
    storage, updater = _dshield_updater(tmp_path, monkeypatch, (
        "999.1.1.1\t999.2.2.2\tx\t1\tbad\tXX\tx@y\n"
        "10.1.0.9\t10.1.0.1\tx\t1\tbad\tXX\tx@y\n"
        "10.2.0.0\t10.2.0.1\n"
        "10.3.0.0\t10.3.0.3\tx\t1\tbad\tXX\tx@y\n"
    ))
    await updater._update_source(None, "Dshield", "https://www.dshield.org/block.txt")
    assert not storage.is_ip_blacklisted("10.1.0.5")
    assert not storage.is_ip_blacklisted("10.2.0.0")
    assert storage.is_ip_blacklisted("10.3.0.3")
