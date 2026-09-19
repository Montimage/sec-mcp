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
        "255.255.255.254\t255.255.255.255\t31\t1\tbad\tXX\tx@y\n"
    ))
    await updater._update_source(None, "Dshield", "https://www.dshield.org/block.txt")
    assert storage.is_ip_blacklisted("10.0.0.7")
    assert storage.is_ip_blacklisted("10.0.0.5")
    assert not storage.is_ip_blacklisted("10.0.0.3")
    assert not storage.is_ip_blacklisted("10.0.0.8")
    assert storage.is_ip_blacklisted("10.1.0.5")
    assert not storage.is_ip_blacklisted("10.1.0.6")
    assert storage.is_ip_blacklisted("255.255.255.255")
    assert storage.is_ip_blacklisted("255.255.255.254")


@pytest.mark.asyncio
async def test_dshield_rejects_malformed_rows(tmp_path, monkeypatch):
    storage, updater = _dshield_updater(tmp_path, monkeypatch, (
        "999.1.1.1\t999.2.2.2\tx\t1\tbad\tXX\tx@y\n"
        "10.1.0.9\t10.1.0.1\tx\t1\tbad\tXX\tx@y\n"
        "10.1.0.9\t::1\tx\t1\tbad\tXX\tx@y\n"
        "10.2.0.0\t10.2.0.1\n"
        "10.3.0.0\t10.3.0.3\tx\t1\tbad\tXX\tx@y\n"
    ))
    await updater._update_source(None, "Dshield", "https://www.dshield.org/block.txt")
    assert not storage.is_ip_blacklisted("10.1.0.5")
    assert not storage.is_ip_blacklisted("10.2.0.0")
    assert storage.is_ip_blacklisted("10.3.0.3")


@pytest.mark.asyncio
async def test_dshield_rejects_oversized_ranges(tmp_path, monkeypatch):
    storage, updater = _dshield_updater(tmp_path, monkeypatch, (
        "1.0.0.0\t2.0.0.0\tx\t1\tbad\tXX\tx@y\n"
        "10.4.0.0\t10.4.255.255\tx\t1\tbad\tXX\tx@y\n"
    ))
    await updater._update_source(None, "Dshield", "https://www.dshield.org/block.txt")
    assert not storage.is_ip_blacklisted("1.0.0.1")
    assert not storage.is_ip_blacklisted("1.255.255.255")
    assert storage.is_ip_blacklisted("10.4.255.255")
    assert storage.is_ip_blacklisted("10.4.0.0")


async def _parsed_entries(source, url, feed_text):
    """Feed a recorded sample through ``_update_source``; return parsed entries.

    The download is mocked so no network is touched; ``add_entries`` receives
    the exact deduplicated ``(url, ip, date, score, source)`` tuples the
    parser produced, in feed order.
    """
    storage = MagicMock(spec=Storage)
    updater = BlacklistUpdater(storage)
    await updater._update_source(_stream_client([feed_text.encode()]), source, url)
    storage.add_entries.assert_called_once()
    return storage.add_entries.call_args[0][0]


@pytest.mark.asyncio
async def test_parse_phishstats_exact_entries():
    entries = await _parsed_entries(
        "PhishStats",
        "https://phishstats.info/phish_score.csv",
        "# phish_score.csv — recorded sample\n"
        "# generated 2025-04-18\n"
        "url,ip,date,score\n"
        "http://evil-phish.example/login,203.0.113.10,2025-04-18 10:00:00,9.5\n"
        "http://second-bad.example/,,,notascore\n",
    )
    assert entries == [
        ("http://evil-phish.example/login", "203.0.113.10", "2025-04-18 10:00:00", 9.5, "PhishStats"),
        # empty ip → None, empty date → now, unparseable score → default 8.0
        ("http://second-bad.example/", None, ANY, 8.0, "PhishStats"),
    ]


@pytest.mark.asyncio
async def test_parse_phishtank_exact_entries():
    entries = await _parsed_entries(
        "PhishTank",
        "https://data.phishtank.com/data/online-valid.csv",
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        "9911,http://phish-one.example/aa,http://detail.example/9911,2025-04-18T10:00:00+00:00,yes,2025-04-18T11:00:00+00:00,yes,Example Bank\n"
        "9922,http://phish-two.example/bb,http://detail.example/9922,2025-04-19T01:02:03+00:00,yes,,yes,Other Corp\n",
    )
    assert entries == [
        ("http://phish-one.example/aa", None, "2025-04-18 10:00:00", 8, "PhishTank"),
        ("http://phish-two.example/bb", None, "2025-04-19 01:02:03", 8, "PhishTank"),
    ]


@pytest.mark.asyncio
async def test_parse_spamhausdrop_exact_entries():
    entries = await _parsed_entries(
        "SpamhausDROP",
        "https://www.spamhaus.org/drop/drop.txt",
        "; Spamhaus DROP list — recorded sample\n"
        "; do not route or peer\n"
        "203.0.113.0/24 ; SBL123456\n"
        "198.51.100.0/25\n",
    )
    assert entries == [
        (None, "203.0.113.0/24", ANY, 8, "SpamhausDROP"),
        (None, "198.51.100.0/25", ANY, 8, "SpamhausDROP"),
    ]


@pytest.mark.asyncio
async def test_parse_dshield_exact_entries():
    entries = await _parsed_entries(
        "Dshield",
        "https://www.dshield.org/block.txt",
        "# DShield.org Recommended Block List\n"
        "Start\tEnd\tNetmask\tAttacks\tName\tCountry\temail\n"
        "10.9.9.0\t10.9.9.15\t255.255.255.240\t100\tbad\tXX\tx@y.example\n"
        "192.0.2.5\t192.0.2.5\t255.255.255.255\t1\tbad\tXX\tx@y.example\n",
    )
    assert entries == [
        # the 16-address range summarizes to a single CIDR block
        (None, "10.9.9.0/28", ANY, 8, "Dshield"),
        # a single-address range is stored as the bare IP
        (None, "192.0.2.5", ANY, 8, "Dshield"),
    ]


@pytest.mark.asyncio
async def test_parse_cinsscore_exact_entries():
    entries = await _parsed_entries(
        "CINSSCORE",
        "https://cinsscore.com/list/ci-badguys.txt",
        "# CINS badguys — recorded sample\n"
        "203.0.113.66\n"
        "198.51.100.23\n",
    )
    assert entries == [
        (None, "203.0.113.66", ANY, 8, "CINSSCORE"),
        (None, "198.51.100.23", ANY, 8, "CINSSCORE"),
    ]


@pytest.mark.asyncio
async def test_parse_emergingthreats_exact_entries():
    entries = await _parsed_entries(
        "EmergingThreats",
        "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
        "# compromised IPs — recorded sample\n"
        "203.0.113.99\n"
        "bad-host.example\n",
    )
    assert entries == [
        (None, "203.0.113.99", ANY, 8, "EmergingThreats"),
        # non-IP entries become URLs with an http:// prefix
        ("http://bad-host.example", None, ANY, 8, "EmergingThreats"),
    ]


@pytest.mark.asyncio
async def test_parse_feodotracker_exact_entries():
    entries = await _parsed_entries(
        "FeodoTracker",
        "https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt",
        "# Feodo Tracker recommended blocklist — recorded sample\n"
        "203.0.113.50\n"
        "203.0.113.51\n",
    )
    assert entries == [
        (None, "203.0.113.50", ANY, 8, "FeodoTracker"),
        (None, "203.0.113.51", ANY, 8, "FeodoTracker"),
    ]


@pytest.mark.asyncio
async def test_parse_blocklistde_exact_entries():
    entries = await _parsed_entries(
        "BlocklistDE",
        "https://lists.blocklist.de/lists/all.txt",
        "203.0.113.77\n",
    )
    assert entries == [
        (None, "203.0.113.77", ANY, 8, "BlocklistDE"),
    ]


@pytest.mark.asyncio
async def test_parse_openphish_exact_entries():
    entries = await _parsed_entries(
        "OpenPhish",
        "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt",
        "http://openphish-bad.example/aa\n"
        "https://openphish-bad2.example/bb\n",
    )
    assert entries == [
        ("http://openphish-bad.example/aa", None, ANY, 8, "OpenPhish"),
        ("https://openphish-bad2.example/bb", None, ANY, 8, "OpenPhish"),
    ]


@pytest.mark.asyncio
async def test_parse_urlhaus_exact_entries():
    entries = await _parsed_entries(
        "URLhaus",
        "https://urlhaus.abuse.ch/downloads/text/",
        "# URLhaus blocklist — recorded sample\n"
        "# generated 2025-04-18\n"
        "http://urlhaus-bad.example/cc\n"
        "https://urlhaus-bad2.example/dd\n",
    )
    assert entries == [
        ("http://urlhaus-bad.example/cc", None, ANY, 8, "URLhaus"),
        ("https://urlhaus-bad2.example/dd", None, ANY, 8, "URLhaus"),
    ]
