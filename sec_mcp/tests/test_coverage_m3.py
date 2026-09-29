"""Coverage-raising tests for the M3 gate (issue #55).

Targets the production-code regions the suite never exercised: CLI text
output branches, the CidrIndex fallback/pytricia legs, EntryIndex mutation
and aggregate helpers, MCP tool error legs, v1 Storage edge paths, feed
parser branches, updater helpers and the start_server entrypoint.
"""

import asyncio
import importlib.util
import json
import logging
import os
import sqlite3
import sys
import time
import types
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from mcp.shared.exceptions import MCPError

from sec_mcp import feed_parsers, mcp_server, start_server, storage_base
from sec_mcp.cli import cli
from sec_mcp.sec_mcp import CheckResult, SecMCP, StatusInfo
from sec_mcp.storage import Storage
from sec_mcp.storage_v2 import HybridStorage
from sec_mcp.storage_v2_index import CidrIndex, EntryIndex, EntryMetadata
from sec_mcp.update_blacklist import BlacklistUpdater

# ``sec_mcp/__init__`` re-exports the name ``cli`` bound to the click Group,
# so the module itself must be pulled out of sys.modules/importlib.
cli_mod = importlib.import_module("sec_mcp.cli")


# ============================================================================
# CLI — non-JSON output branches and the commands no test invoked
# ============================================================================

class _FakeStorage:
    """Storage surface the CLI touches (status/flush_cache)."""

    def __init__(self, cleared=True):
        self._cleared = cleared

    def get_source_counts(self):
        return {"FeedA": 2, "FeedB": 1}

    def get_source_type_counts(self):
        return {"FeedA": {"domain": 1, "url": 1, "ip": 0},
                "FeedB": {"domain": 0, "url": 0, "ip": 1}}

    def flush_cache(self):
        return self._cleared


class _FakeCore:
    """Deterministic SecMCP stand-in for CLI output-path tests."""

    def __init__(self):
        self.storage = _FakeStorage()
        self.blacklisted = {"evil.com", "http://evil.com/x", "1.2.3.4"}
        self.update_result = {"updated": True}

    def _result(self, value):
        return CheckResult(value in self.blacklisted, f"lookup {value}")

    def check(self, value):
        return self._result(value)

    def check_domain(self, domain):
        return self._result(domain)

    def check_url(self, url):
        return self._result(url)

    def check_ip(self, ip):
        return self._result(ip)

    def check_batch(self, values):
        return [self._result(v) for v in values]

    def get_status(self):
        return StatusInfo(
            entry_count=3,
            last_update=datetime(2026, 1, 1, 12, 0, 0),
            sources=["FeedA", "FeedB"],
            server_status="Running (STDIO)",
        )

    def update(self):
        return self.update_result

    def sample(self, count):
        return [f"entry{i}" for i in range(count)]


@pytest.fixture
def fake_core(monkeypatch):
    core = _FakeCore()
    monkeypatch.setattr(cli_mod, "get_core", lambda: core)
    return core


@pytest.mark.parametrize("command,value", [
    ("check", "evil.com"),
    ("check-domain", "evil.com"),
    ("check-url", "http://evil.com/x"),
    ("check-ip", "1.2.3.4"),
])
def test_cli_text_output_blacklisted(fake_core, command, value):
    result = CliRunner().invoke(cli, [command, value])
    assert result.exit_code == 0, result.output
    assert "Status: Blacklisted" in result.output
    assert "Explanation:" in result.output


@pytest.mark.parametrize("command,value", [
    ("check", "safe.com"),
    ("check-domain", "safe.com"),
    ("check-url", "http://safe.com/x"),
    ("check-ip", "9.9.9.9"),
])
def test_cli_text_output_safe(fake_core, command, value):
    result = CliRunner().invoke(cli, [command, value])
    assert result.exit_code == 0, result.output
    assert "Status: Safe" in result.output


def test_cli_batch_text_and_json(fake_core, tmp_path):
    batch_file = tmp_path / "batch.txt"
    batch_file.write_text("evil.com\nsafe.com\n")

    result = CliRunner().invoke(cli, ["batch", str(batch_file)])
    assert result.exit_code == 0, result.output
    assert "evil.com:" in result.output
    assert "Status: Blacklisted" in result.output
    assert "Status: Safe" in result.output

    result = CliRunner().invoke(cli, ["batch", str(batch_file), "--json"])
    assert result.exit_code == 0, result.output
    assert '"is_safe"' in result.output


def test_cli_status_text_and_json(fake_core):
    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0, result.output
    assert "Total entries: 3" in result.output
    assert "FeedA" in result.output
    assert "Server status:" in result.output

    result = CliRunner().invoke(cli, ["status", "--json"])
    assert result.exit_code == 0, result.output
    assert '"entry_count": 3' in result.output
    assert '"source_counts"' in result.output


@pytest.mark.parametrize("update_result,needle", [
    ({"updated": True}, "Blacklist update triggered."),
    ({"updated": False, "reason": "rate limited"}, "update skipped"),
    (None, "Blacklist update triggered."),  # None -> {"updated": True}
])
def test_cli_update_branches(fake_core, update_result, needle):
    fake_core.update_result = update_result
    result = CliRunner().invoke(cli, ["update"])
    assert result.exit_code == 0, result.output
    assert needle in result.output


def test_cli_update_json(fake_core):
    result = CliRunner().invoke(cli, ["update", "--json"])
    assert result.exit_code == 0, result.output
    assert '"updated": true' in result.output


def test_cli_flush_cache_branches(fake_core):
    result = CliRunner().invoke(cli, ["flush-cache"])
    assert result.exit_code == 0, result.output
    assert "cleared" in result.output

    fake_core.storage._cleared = False
    result = CliRunner().invoke(cli, ["flush-cache"])
    assert "already empty" in result.output

    result = CliRunner().invoke(cli, ["flush-cache", "--json"])
    assert '"cleared": false' in result.output


def test_cli_sample(fake_core):
    result = CliRunner().invoke(cli, ["sample", "-n", "3"])
    assert result.exit_code == 0, result.output
    assert result.output.count("entry") == 3


# ============================================================================
# Direct-file-load ImportError fallbacks (benchmark.py's load pattern)
# ============================================================================

@pytest.mark.parametrize("module_name", [
    "storage_v2_index", "storage_v2_writes", "storage_v2_db", "storage_v2",
])
def test_module_loads_without_package_context(module_name):
    """spec_from_file_location has no package context: the relative import
    fails and the absolute fallback must still resolve."""
    path = Path(__file__).resolve().parent.parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"_bare_{module_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__name__ == f"_bare_{module_name}"


# ============================================================================
# CidrIndex — both radix-tree and pure-python backends
# ============================================================================

def _cidr_index(use_pytricia, monkeypatch):
    if not use_pytricia:
        monkeypatch.setitem(sys.modules, "pytricia", None)
    return CidrIndex()


@pytest.mark.parametrize("use_pytricia", [True, False], ids=["pytricia", "fallback"])
class TestCidrIndex:
    def test_add_has_source_remove(self, use_pytricia, monkeypatch):
        idx = _cidr_index(use_pytricia, monkeypatch)
        meta = EntryMetadata("Spamhaus", "2025-01-01", 9.0)

        idx.add("10.0.0.0/8", "Spamhaus", meta)
        idx.add("2001:db8::/32", "Spamhaus", meta)

        assert idx.has("10.1.2.3") is True
        assert idx.has("2001:db8::1") is True
        assert idx.has("11.0.0.1") is False
        assert idx.source("10.1.2.3") == "Spamhaus"
        assert idx.source("2001:db8::1") == "Spamhaus"
        assert idx.source("11.0.0.1") is None
        assert idx.has_range("10.0.0.0/8") is True
        assert idx.count() == 2
        assert "10.0.0.0/8" in idx.keys()
        assert meta in idx.metadata_values()

        idx.remove("10.0.0.0/8")
        assert idx.has("10.1.2.3") is False
        # Removing a range that is not stored is a no-op.
        idx.remove("10.0.0.0/8")
        if not use_pytricia:
            # The fallback matcher also swallows a malformed key; the tree
            # backend never sees one through the public API (has_range gates).
            idx.remove("not-a-network")

    def test_malformed_lookups_never_raise(self, use_pytricia, monkeypatch):
        idx = _cidr_index(use_pytricia, monkeypatch)
        idx.add("10.0.0.0/8", "s", EntryMetadata("s", "d", 1.0))
        assert idx.has("not-an-ip") is False
        assert idx.has("999.1.1.1") is False
        assert idx.source("not-an-ip") is None

    def test_add_rejects_invalid(self, use_pytricia, monkeypatch):
        idx = _cidr_index(use_pytricia, monkeypatch)
        meta = EntryMetadata("s", "d", 1.0)
        with pytest.raises(ValueError):
            idx.add("not-a-network", "s", meta)
        assert idx.try_add("not-a-network", "s", meta) is False
        assert idx.try_add("10.9.0.0/16", "s", meta) is True
        assert idx.has("10.9.9.9") is True

    def test_load_and_discard(self, use_pytricia, monkeypatch):
        idx = _cidr_index(use_pytricia, monkeypatch)
        meta = EntryMetadata("s", "d", 1.0)
        assert idx.load("192.168.0.0/16", meta) == 1
        if use_pytricia:
            # Tree-insert errors propagate to the row loop's handler.
            with pytest.raises((ValueError, SystemError)):
                idx.load("bad-range/99", meta)
        else:
            assert idx.load("bad-range/99", meta) == 0
        idx.discard("192.168.0.0/16")
        assert idx.has("192.168.1.1") is False

    def test_empty_like_keeps_backend(self, use_pytricia, monkeypatch):
        idx = _cidr_index(use_pytricia, monkeypatch)
        idx.add("10.0.0.0/8", "s", EntryMetadata("s", "d", 1.0))
        clone = idx.empty_like()
        assert clone._use_pytricia == idx._use_pytricia
        assert clone.count() == 0
        clone.add("172.16.0.0/12", "s", EntryMetadata("s", "d", 1.0))
        assert clone.has("172.16.5.5") is True


# ============================================================================
# EntryIndex — mutation helpers, aggregates, row loads, lookups
# ============================================================================

@pytest.fixture
def index():
    idx = EntryIndex()
    meta = EntryMetadata("FeedA", "2025-01-01", 9.0)
    idx.add_domain("evil.com", meta)
    idx.add_url("http://evil.com/x", meta)
    idx.add_ip("1.2.3.4", "FeedA", meta)          # IPv4 -> int pool
    idx.add_ip("2001:db8::1", "FeedA", meta)      # IPv6 -> str pool
    idx.add_ip("10.0.0.0/8", "FeedB", EntryMetadata("FeedB", "2025-01-01", 8.0))
    return idx


class TestEntryIndex:
    def test_mutation_and_discard(self, index):
        index.discard_domain("evil.com")
        assert index.has_domain("evil.com") is False

        index.discard_url("http://evil.com/x")
        assert index.has_url("http://evil.com/x") is False

        index.discard_ip("10.0.0.0/8", is_cidr=True, ip_int=None)
        assert index._cidr.has_range("10.0.0.0/8") is False

        index.discard_ip("1.2.3.4", is_cidr=False, ip_int=16909060)
        assert index.has_ip("1.2.3.4") is False

        index.discard_ip("2001:db8::1", is_cidr=False, ip_int=None)
        assert index.has_ip("2001:db8::1") is False

    def test_batch_memory_inserts_and_remove(self, index):
        index.add_domains([("b1.com", "d", 1.0, "s"), ("b2.com", "d", 1.0, "s")])
        assert index.has_domain("b1.com") is True

        index.add_urls([("HTTP://B3.com/", "d", 1.0, "s")])
        assert index.has_url("http://b3.com") is True

        index.add_ips([
            ("9.9.9.9", "d", 1.0, "s"),
            ("2001:db8::5", "d", 1.0, "s"),   # IPv6 -> string pool
            ("bad", "d", 1.0, "s"),           # rejected, stored nowhere
        ])
        assert index.has_ip("9.9.9.9") is True
        assert index.has_ip("2001:db8::5") is True

        # remove() drops a value from whichever pools hold it.
        assert index.remove("b1.com", "b1.com") is True
        assert index.remove("http://evil.com/x", "http://evil.com/x") is True
        assert index.remove("1.2.3.4", "1.2.3.4") is True
        assert index.remove("2001:db8::1", "2001:db8::1") is True
        assert index.remove("10.0.0.0/8", "10.0.0.0/8") is True
        assert index.remove("absent.com", "absent.com") is False

    def test_aggregates_and_sample(self, index):
        assert index.count() == 5
        counts = index.source_counts()
        assert counts["FeedA"] == 4 and counts["FeedB"] == 1
        types_ = index.source_type_counts()
        assert types_["FeedA"] == {"domain": 1, "url": 1, "ip": 2}
        assert types_["FeedB"] == {"domain": 0, "url": 0, "ip": 1}
        assert set(index.active_sources()) == {"FeedA", "FeedB"}

        assert index.sample(0) == []
        assert len(index.sample(99)) == 5
        sample = index.sample(3)
        assert len(sample) == 3 and len(set(sample)) == 3

    def test_row_loads_skip_malformed(self):
        idx = EntryIndex()
        assert idx.load_domains([("ok.com", "s", "d", 1.0), (None, "s", "d", 1.0), (5, "s", "d", 1.0)]) == 1
        # Already-canonical URL -> normalized_count 0; mixed-case URL -> 1.
        assert idx.load_urls([("http://ok.com", "s", "d", 1.0), (None, "s", "d", 1.0)]) == 0
        assert idx.load_urls([("HTTP://UP.com/", "s", "d", 1.0)]) == 1  # normalized
        # bad single values raise; bad CIDRs are counted as errors
        loaded_int = idx.load_ips([
            ("1.2.3.4", "s", "d", 1.0),
            ("2001:db8::9", "s", "d", 1.0),
            ("10.0.0.0/8", "s", "d", 1.0),
            ("10.0.0.0/99", "s", "d", 1.0),
            (None, "s", "d", 1.0),
        ])
        assert loaded_int == 1
        assert idx.has_ip("1.2.3.4") is True
        assert idx.has_ip("2001:db8::9") is True
        assert idx.has_ip("10.1.1.1") is True

    def test_membership_and_source_attribution(self, index):
        assert index.has_domain("sub.evil.com") is True
        assert index.has_domain("other.com") is False
        assert index.has_url("http://evil.com/x") is True
        assert index.has_url("http://evil.com/y") is False
        assert index.has_ip("1.2.3.4") is True
        assert index.has_ip("2001:db8::1") is True
        assert index.has_ip("10.5.5.5") is True     # via CIDR
        assert index.has_ip("bad-input") is False
        assert index.has_ip("8.8.8.8") is False

        assert index.domain_source("sub.evil.com") == "FeedA"
        assert index.domain_source("other.com") is None
        assert index.url_source("http://evil.com/x") == "FeedA"
        assert index.url_source("http://evil.com/y") is None
        assert index.ip_source("1.2.3.4") == "FeedA"
        assert index.ip_source("2001:db8::1") == "FeedA"
        assert index.ip_source("10.5.5.5") == "FeedB"   # via CIDR
        assert index.ip_source("bad-input") is None
        assert index.ip_source("8.8.8.8") is None

    def test_empty_like(self, index):
        clone = index.empty_like()
        assert clone.count() == 0
        assert clone.has_domain("evil.com") is False
        clone.add_domain("new.com", EntryMetadata("s", "d", 1.0))
        assert clone.has_domain("new.com") is True


# ============================================================================
# HybridStorage — getattr seam, metrics, flush, write rollbacks
# ============================================================================

@pytest.fixture
def v2(tmp_path):
    return HybridStorage(str(tmp_path / "v2.db"))


class TestHybridStorageEdges:
    def test_getattr_seam(self, v2):
        assert isinstance(v2._domains, set)            # _INDEX_ATTRS leg
        assert v2._use_pytricia in (True, False)       # _CIDR_ATTRS leg
        with pytest.raises(AttributeError):
            v2.no_such_attribute                       # AttributeError leg

    def test_metrics_without_psutil(self, v2, monkeypatch):
        monkeypatch.setitem(sys.modules, "psutil", None)
        metrics = v2.get_metrics()
        assert metrics["memory_usage_mb"] == "0.0"
        assert "total_lookups" in metrics

    def test_flush_cache(self, v2, monkeypatch):
        assert v2.flush_cache() is True

        def _boom():
            raise sqlite3.OperationalError("corrupt")
        monkeypatch.setattr(v2, "_load_all_data", _boom)
        assert v2.flush_cache() is False

    def test_single_write_rollback_on_db_failure(self, v2, monkeypatch):
        monkeypatch.setattr(
            v2._db, "upsert_domain",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
        with pytest.raises(sqlite3.OperationalError):
            v2.add_domain("evil.com", "2025-01-01", 9.0, "test")
        assert v2.is_domain_blacklisted("evil.com") is False

        monkeypatch.setattr(
            v2._db, "upsert_url",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
        with pytest.raises(sqlite3.OperationalError):
            v2.add_url("http://evil.com/x", "2025-01-01", 9.0, "test")
        assert v2.is_url_blacklisted("http://evil.com/x") is False

    def test_ip_write_rollback_covers_all_pools(self, v2, monkeypatch):
        monkeypatch.setattr(
            v2._db, "upsert_ip",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
        # IPv4 -> int pool rollback
        with pytest.raises(sqlite3.OperationalError):
            v2.add_ip("1.2.3.4", "2025-01-01", 9.0, "test")
        assert v2.is_ip_blacklisted("1.2.3.4") is False
        # IPv6 -> str pool rollback
        with pytest.raises(sqlite3.OperationalError):
            v2.add_ip("2001:db8::7", "2025-01-01", 9.0, "test")
        assert v2.is_ip_blacklisted("2001:db8::7") is False

    def test_batch_write_failure_reloads_from_db(self, v2, monkeypatch):
        monkeypatch.setattr(
            v2._db, "upsert_domains",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
        with pytest.raises(sqlite3.OperationalError):
            v2.add_domains([("e1.com", "2025-01-01", 9.0, "t")])
        assert v2.is_domain_blacklisted("e1.com") is False

        monkeypatch.setattr(
            v2._db, "upsert_urls",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
        with pytest.raises(sqlite3.OperationalError):
            v2.add_urls([("http://e2.com/x", "2025-01-01", 9.0, "t")])
        assert v2.is_url_blacklisted("http://e2.com/x") is False

        monkeypatch.setattr(
            v2._db, "upsert_ips",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
        with pytest.raises(sqlite3.OperationalError):
            v2.add_ips([("3.3.3.3", "2025-01-01", 9.0, "t")])
        assert v2.is_ip_blacklisted("3.3.3.3") is False

    def test_add_entries_skips_malformed_url(self, v2):
        # urlparse raises on the unbalanced IPv6 bracket -> row dropped.
        v2.add_entries([("http://[::1", None, "2025-01-01", 8.0, "t")])
        assert v2.count_entries() == 0


# ============================================================================
# v1 Storage + storage_queries + storage_base edge paths
# ============================================================================

class TestStorageV1Edges:
    def test_db_dir_creation_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            os, "makedirs",
            lambda *a, **k: (_ for _ in ()).throw(OSError("read-only fs")))
        with pytest.raises(RuntimeError, match="Cannot create database directory"):
            Storage(str(tmp_path / "sub" / "db.db"))

    def test_cache_size_bad_config_falls_back(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sec_mcp.storage.load_config", lambda: {"cache_size": "bogus"})
        storage = Storage(str(tmp_path / "db.db"))
        assert storage._cache_max_size == 10000

    def test_init_db_failure_is_runtime_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            storage_base, "init_db",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
        with pytest.raises(RuntimeError, match="Cannot initialize database"):
            Storage(str(tmp_path / "db.db"))

    def test_cidr_entries_skip_invalid_networks(self, tmp_path):
        storage = Storage(str(tmp_path / "db.db"))
        # A corrupt netmask row must be skipped, not crash the range scan.
        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "INSERT INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
            ("not/a/network", "2025-01-01", 9.0, "corrupt"))
        conn.execute(
            "INSERT INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
            ("10.0.0.0/8", "2025-01-01", 9.0, "Spamhaus"))
        conn.commit()
        conn.close()

        assert storage.is_ip_blacklisted("10.1.2.3") is True
        # Second lookup replays from the positive-hit cache.
        assert storage.is_ip_blacklisted("10.1.2.3") is True
        # Malformed input short-circuits before any table access.
        assert storage.is_ip_blacklisted("not-an-ip") is False

    def test_add_ip_write_failure_is_runtime_error(self, tmp_path):
        storage = Storage(str(tmp_path / "db.db"))
        conn = sqlite3.connect(storage.db_path)
        conn.execute("DROP TABLE blacklist_ip")
        conn.commit()
        conn.close()
        with pytest.raises(RuntimeError, match="Cannot write to database"):
            storage.add_ip("1.2.3.4", "2025-01-01", 9.0, "test")

    def test_flush_cache_clears(self, tmp_path):
        storage = Storage(str(tmp_path / "db.db"))
        storage.add_ip("10.0.0.0/8", "2025-01-01", 9.0, "t")
        assert storage.is_ip_blacklisted("10.1.1.1") is True
        assert storage.flush_cache() is True

    def test_query_edges(self, tmp_path):
        storage = Storage(str(tmp_path / "db.db"))
        storage.add_domain("evil.com", "2025-01-01", 9.0, "FeedA")
        storage.add_url("http://evil.com/x", "2025-01-01", 8.0, "FeedB")
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "FeedA")
        storage.log_update("FeedA", 3)

        # CIDR-member source attribution and the malformed-IP early return.
        assert storage.get_ip_blacklist_source("10.9.9.9") == "FeedA"
        assert storage.get_ip_blacklist_source("garbage") is None

        types_ = storage.get_source_type_counts()
        assert types_["FeedA"] == {"domain": 1, "url": 0, "ip": 1}
        assert types_["FeedB"] == {"domain": 0, "url": 1, "ip": 0}

        sample = storage.sample_entries(5)
        assert 1 <= len(sample) <= 5
        assert "FeedA" in storage.get_active_sources()
        assert storage.get_last_update_per_source()["FeedA"]
        history = storage.get_update_history(source="FeedA")
        assert len(history) == 1 and history[0]["entry_count"] == 3

    def test_classify_feed_entries_buckets(self, tmp_path):
        storage = Storage(str(tmp_path / "db.db"))
        storage.add_entries([
            ("http://domain-only.com", None, "d", 8.0, "s"),      # domain bucket
            ("http://has-path.com/p", None, "d", 8.0, "s"),       # url bucket
            (None, "5.5.5.5", "d", 8.0, "s"),                     # ip bucket
            ("http://[::1", None, "d", 8.0, "s"),                 # urlparse rejects -> dropped
        ])
        assert storage.is_domain_blacklisted("domain-only.com") is True
        assert storage.is_url_blacklisted("http://has-path.com/p") is True
        assert storage.is_ip_blacklisted("5.5.5.5") is True
        assert storage.count_entries() == 3


class TestStorageBaseEdges:
    @pytest.mark.parametrize("os_name,platform", [
        ("nt", "win32"), ("posix", "darwin"), ("posix", "linux"), ("java", "linux"),
    ])
    def test_default_db_path_fallbacks(self, monkeypatch, tmp_path, os_name, platform):
        # platformdirs missing -> per-OS conventions; home redirected to tmp.
        monkeypatch.setitem(sys.modules, "platformdirs", None)
        monkeypatch.setattr(os, "name", os_name)
        monkeypatch.setattr(sys, "platform", platform)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))

        path = storage_base.get_default_db_path()
        assert path.endswith(storage_base.DEFAULT_DB_FILENAME)
        assert str(tmp_path) in path

    def test_default_db_path_via_platformdirs(self):
        # The primary leg: platformdirs resolves the per-user data dir.
        path = storage_base.get_default_db_path()
        assert path.endswith(storage_base.DEFAULT_DB_FILENAME)
        assert "sec-mcp" in path

    def test_resolve_db_path_env_and_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv(storage_base.DB_ENV_VAR, "/env/db.db")
        assert storage_base.resolve_db_path() == "/env/db.db"
        assert storage_base.resolve_db_path("/arg/db.db") == "/arg/db.db"

        monkeypatch.delenv(storage_base.DB_ENV_VAR)
        monkeypatch.setattr(
            storage_base, "get_default_db_path", lambda: str(tmp_path / "d.db"))
        assert storage_base.resolve_db_path() == str(tmp_path / "d.db")

    def test_normalize_url_malformed_returns_lowered(self):
        # urlparse raises ValueError on the unbalanced IPv6 bracket.
        assert storage_base.normalize_url("HTTP://[::1") == "http://[::1"


# ============================================================================
# FeedParser branches
# ============================================================================

class _FakeUpdater:
    def __init__(self, max_range_addresses=1 << 16):
        self.logger = logging.getLogger("test.feed_parsers")
        self.max_range_addresses = max_range_addresses


@pytest.fixture
def parser():
    return feed_parsers.FeedParser(_FakeUpdater())


class TestFeedParserEdges:
    def test_parse_failure_returns_none(self, parser, monkeypatch):
        def _boom(self, source, content):
            raise RuntimeError("bad feed")
        monkeypatch.setitem(feed_parsers.FeedParser._PARSERS, "Boom", _boom)
        assert parser.parse("Boom", "content") is None

    def test_phishstats_header_only_and_bad_score(self, parser):
        assert parser.parse("PhishStats", "url,ip,date,score\n") is None
        entries = parser.parse(
            "PhishStats",
            "url,ip,date,score\n"
            "http://p.com/x,1.1.1.1,2025-01-01,notanumber\n")
        assert entries == [("http://p.com/x", "1.1.1.1", "2025-01-01", 8.0, "PhishStats")]

    def test_phishtank_rows(self, parser):
        entries = parser.parse(
            "PhishTank",
            "url,submission_time,target\nhttp://t.com/x,2025-01-01T00:00:00+00:00,Bank\n")
        assert entries[0][0] == "http://t.com/x"
        assert entries[0][3] == 8

    def test_spamhausdrop_skips_comments_and_blanks(self, parser):
        entries = parser.parse(
            "SpamhausDROP",
            "; comment line\n\n10.0.0.0/8 ; SBL123\n192.168.0.0/16\n")
        assert [e[1] for e in entries] == ["10.0.0.0/8", "192.168.0.0/16"]

    def test_dshield_ranges_and_skips(self):
        parser = feed_parsers.FeedParser(_FakeUpdater(max_range_addresses=4))
        entries = parser.parse(
            "Dshield",
            "# comment\nStart\tEnd\tNetmask\n"
            "1.0.0.0\t1.0.0.1\t31\n"           # 2 addresses -> kept
            "2.0.0.0\t2.0.0.9\t29\n"           # 10 > cap -> skipped
            "x\ty\tz\n"                        # unparseable IPs -> skipped
            "bogus\trow\n")                    # too few fields -> skipped
        # summarize_address_range coalesces the pair into one /31 network.
        assert [e[1] for e in entries] == ["1.0.0.0/31"]

    def test_cinsscore_lines(self, parser):
        entries = parser.parse("CINSSCORE", "# c\n1.1.1.1\n\n2.2.2.2\n")
        assert [e[1] for e in entries] == ["1.1.1.1", "2.2.2.2"]

    def test_ip_or_domain_lines(self, parser):
        entries = parser.parse(
            "EmergingThreats",
            "# c\n9.9.9.9\nevil.com\nhttp://already.com/x\n")
        assert entries[0] == (None, "9.9.9.9", entries[0][2], 8, "EmergingThreats")
        assert entries[1][0] == "http://evil.com"
        assert entries[2][0] == "http://already.com/x"

    def test_generic_parser_csv_and_bare_values(self, parser):
        entries = parser.parse(
            "UnknownFeed",
            "# comment\n\n"
            "http://csv.com/x,1.1.1.1,2025-01-01,badscore\n"  # CSV, bad score -> 8
            "8.8.8.8\n"                                        # bare IP
            "bare-domain.com\n"                                # bare domain -> http prefix
            "!!! invalid !!!\n")                               # validate_input rejects
        assert entries[0] == ("http://csv.com/x", "1.1.1.1", "2025-01-01", 8, "UnknownFeed")
        assert entries[1][1] == "8.8.8.8"
        assert entries[2][0] == "http://bare-domain.com"
        assert all("invalid" not in (e[0] or "") for e in entries)

    def test_dedupe_keys_on_ip_then_url(self, parser):
        entries = [
            ("http://a.com", "1.1.1.1", "d", 8, "s"),
            ("http://b.com", "1.1.1.1", "d", 8, "s"),   # same ip -> dropped
            ("http://a.com", None, "d", 8, "s"),
            ("http://a.com", None, "d", 8, "s"),        # same url -> dropped
            (None, None, "d", 8, "s"),                  # no key -> dropped
        ]
        deduped = feed_parsers.FeedParser.dedupe(entries)
        assert deduped == [entries[0], entries[2]]


# ============================================================================
# BlacklistUpdater helpers — cache read, scheduler loop, update paths
# ============================================================================

def _updater(tmp_path, sources=None):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"blacklist_sources": sources or {}, "log_level": "INFO"}))
    return BlacklistUpdater(Storage(str(tmp_path / "up.db")), config_path=str(cfg))


class TestBlacklistUpdaterEdges:
    def test_read_cached_feed(self, tmp_path):
        updater = _updater(tmp_path)
        feed = tmp_path / "feed.txt"

        assert updater._read_cached_feed(str(feed)) is None          # missing

        feed.write_bytes(b"data")
        assert updater._read_cached_feed(str(feed)) == b"data"       # fresh

        old = time.time() - 2 * 86400
        os.utime(feed, (old, old))
        assert updater._read_cached_feed(str(feed)) is None          # stale

        fresh = tmp_path / "big.txt"
        fresh.write_bytes(b"x" * 10)
        updater.max_feed_bytes = 3
        assert updater._read_cached_feed(str(fresh)) is None         # oversize

    def test_scheduler_loop_and_tick(self, monkeypatch):
        class _Stop:
            def __init__(self):
                self.calls = 0
            def wait(self, timeout):
                self.calls += 1
                return self.calls > 1   # tick once, then exit
        class _Sched:
            def __init__(self):
                self.ran = 0
            def run_pending(self):
                self.ran += 1

        sched = _Sched()
        monkeypatch.setattr(BlacklistUpdater, "_scheduler_stop", _Stop())
        monkeypatch.setattr(BlacklistUpdater, "_scheduler", sched)
        BlacklistUpdater._scheduler_loop()
        assert sched.ran == 1

        # Early returns: no stop event, or stop already set, or no scheduler.
        monkeypatch.setattr(BlacklistUpdater, "_scheduler_stop", None)
        BlacklistUpdater._scheduler_loop()
        monkeypatch.setattr(BlacklistUpdater, "_scheduler_stop", _Stop())
        monkeypatch.setattr(BlacklistUpdater, "_scheduler", None)
        BlacklistUpdater._scheduler_loop()

    def test_scheduler_tick_survives_job_failure(self):
        class _Boom:
            def run_pending(self):
                raise RuntimeError("job blew up")
        BlacklistUpdater._scheduler_tick(_Boom())   # logs, never raises

    def test_update_all_progress_callback_and_non_https(self, tmp_path):
        updater = _updater(tmp_path, {"Insecure": "http://feed.example/x"})
        updater.progress_callback = lambda *a: (_ for _ in ()).throw(RuntimeError("cb"))
        asyncio.run(updater.update_all())   # callback failure logged, not raised

    def test_update_source_full_path(self, tmp_path, monkeypatch):
        updater = _updater(tmp_path)

        async def _fake_fetch(client, source, url, filename):
            return "1.2.3.4\n5.6.7.8\n", False
        monkeypatch.setattr(updater, "_fetch_feed", _fake_fetch)
        asyncio.run(updater._update_source(None, "CINSSCORE", "https://feed.example/l.txt"))
        assert updater.storage.is_ip_blacklisted("1.2.3.4") is True
        assert updater.storage.count_entries() == 2

        # Cached content (use_cache=True) skips the cache write.
        async def _cached_fetch(client, source, url, filename):
            return "9.9.9.9\n", True
        monkeypatch.setattr(updater, "_fetch_feed", _cached_fetch)
        asyncio.run(updater._update_source(None, "CINSSCORE", "https://feed.example/l.txt"))
        assert updater.storage.is_ip_blacklisted("9.9.9.9") is True

        # A parse that yields None aborts before any storage write.
        async def _bad_fetch(client, source, url, filename):
            return "url,ip,date,score\n", False   # PhishStats: header only -> None
        monkeypatch.setattr(updater, "_fetch_feed", _bad_fetch)
        before = updater.storage.count_entries()
        asyncio.run(updater._update_source(None, "PhishStats", "https://feed.example/p.csv"))
        assert updater.storage.count_entries() == before

    def test_update_source_sanity_rejects_implausible_feed(self, tmp_path, monkeypatch):
        updater = _updater(tmp_path)
        updater.min_feed_entries = 10   # a 2-entry feed fails the sanity check
        async def _fake_fetch(client, source, url, filename):
            return "1.2.3.4\n5.6.7.8\n", False
        monkeypatch.setattr(updater, "_fetch_feed", _fake_fetch)
        asyncio.run(updater._update_source(None, "CINSSCORE", "https://f.example/l.txt"))
        assert updater.storage.count_entries() == 0

    def test_update_source_failure_is_logged_not_raised(self, tmp_path, monkeypatch):
        updater = _updater(tmp_path)
        async def _boom(client, source, url, filename):
            raise RuntimeError("network down")
        monkeypatch.setattr(updater, "_fetch_feed", _boom)
        asyncio.run(updater._update_source(None, "CINSSCORE", "https://f.example/l.txt"))

    def test_force_update_rate_limit_and_success(self, tmp_path):
        updater = _updater(tmp_path)   # zero sources -> update_all is a no-op
        assert updater.force_update() == {"updated": True}

        updater.min_update_interval = 9999
        refused = updater.force_update()
        assert refused["updated"] is False
        assert "rate limited" in refused["reason"]

    def test_feed_cache_filename_extension(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
        updater = _updater(tmp_path)
        assert updater._feed_cache_filename("S", "https://x/f.csv").endswith(".csv")
        assert updater._feed_cache_filename("S", "https://x/f").endswith(".txt")
        # Source names are sanitized to filesystem-safe characters.
        assert os.path.basename(
            updater._feed_cache_filename("a/b c", "https://x/f")) == "a_b_c.txt"


# ============================================================================
# MCP server tools — error legs and diagnostics modes
# ============================================================================

@pytest.fixture
def mcp_core(tmp_path, monkeypatch):
    """Real shared core with its storage swapped for a seeded v2 store."""
    core = mcp_server.get_core()
    storage = HybridStorage(str(tmp_path / "mcp.db"))
    storage.add_domain("evil.com", "2025-01-01", 9.0, "FeedA")
    storage.add_ip("1.2.3.4", "2025-01-01", 9.0, "FeedA")
    monkeypatch.setattr(core, "storage", storage)
    return core


class TestMcpServerEdges:
    async def test_check_batch_verdicts_and_error(self, mcp_core, monkeypatch):
        result = await mcp_server.check_batch(["evil.com", "ok.com", "!!! bad"])
        verdicts = {item["value"]: item["verdict"] for item in result}
        assert verdicts["evil.com"] == "blacklisted"
        assert verdicts["ok.com"] == "safe"
        assert verdicts["!!! bad"] == "invalid"

        monkeypatch.setattr(
            mcp_core, "check",
            lambda v: (_ for _ in ()).throw(ValueError("store down")))
        result = await mcp_server.check_batch(["x.com"])
        assert result.is_error is True

        monkeypatch.setattr(
            mcp_core, "check",
            lambda v: (_ for _ in ()).throw(MCPError(code=-32000, message="proto")))
        with pytest.raises(MCPError):
            await mcp_server.check_batch(["x.com"])

    async def test_get_status_and_error_leg(self, mcp_core, monkeypatch):
        result = await mcp_server.get_status()
        assert result["entry_count"] == 2
        assert result["scheduler_alive"] is False

        monkeypatch.setattr(
            mcp_core, "get_status",
            lambda: (_ for _ in ()).throw(RuntimeError("gone")))
        result = await mcp_server.get_status()
        assert result.is_error is True

        monkeypatch.setattr(
            mcp_core, "get_status",
            lambda: (_ for _ in ()).throw(MCPError(code=-32000, message="proto")))
        with pytest.raises(MCPError):
            await mcp_server.get_status()

    async def test_update_blacklists_progress_and_result(self, mcp_core, monkeypatch):
        ctx = types.SimpleNamespace(report_progress=lambda *a: None)
        updater = mcp_core.updater

        def _update_with_progress():
            # Fire the installed progress callback like a real update does.
            updater.progress_callback("FeedA", 1, 2)
            return {"updated": True}
        monkeypatch.setattr(mcp_core, "update", _update_with_progress)
        # Force the anyio bridge to fail: the RuntimeError leg is best-effort.
        monkeypatch.setattr(
            mcp_server.anyio.from_thread, "run",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no loop")))
        result = await mcp_server.update_blacklists(ctx)
        assert result == {"updated": True}
        # Our callback was cleared afterwards; a foreign one survives.
        assert updater.progress_callback is None

    async def test_update_blacklists_none_result_and_error(self, mcp_core, monkeypatch):
        ctx = types.SimpleNamespace(report_progress=lambda *a: None)
        monkeypatch.setattr(mcp_core, "update", lambda: None)
        result = await mcp_server.update_blacklists(ctx)
        assert result == {"updated": True}

        monkeypatch.setattr(
            mcp_core, "update",
            lambda: (_ for _ in ()).throw(RuntimeError("down")))
        result = await mcp_server.update_blacklists(ctx)
        assert result.is_error is True

        monkeypatch.setattr(
            mcp_core, "update",
            lambda: (_ for _ in ()).throw(MCPError(code=-32000, message="proto")))
        with pytest.raises(MCPError):
            await mcp_server.update_blacklists(ctx)

    async def test_diagnostics_all_modes(self, mcp_core, monkeypatch):
        assert (await mcp_server.get_diagnostics(mode="summary"))["mode"] == "summary"

        full = await mcp_server.get_diagnostics(mode="full")
        assert full["mode"] == "full"
        assert full["health"]["db_ok"] is True
        assert full["performance"]["total_lookups"] >= 0

        health = await mcp_server.get_diagnostics(mode="health")
        assert health["db_ok"] is True

        perf = await mcp_server.get_diagnostics(mode="performance")
        assert perf["mode"] == "performance"
        assert "total_lookups" in perf

        sample = await mcp_server.get_diagnostics(mode="sample", sample_count=1)
        assert sample["mode"] == "sample" and sample["count"] == 1

    async def test_diagnostics_v1_storage_and_db_failure(self, mcp_core, tmp_path, monkeypatch):
        # v1 Storage has no get_metrics -> the performance error payload.
        monkeypatch.setattr(mcp_core, "storage", Storage(str(tmp_path / "v1.db")))
        perf = await mcp_server.get_diagnostics(mode="performance")
        assert perf["error"] == "Metrics not available"
        full = await mcp_server.get_diagnostics(mode="full")
        assert full["performance"] == {"available": False}

    async def test_diagnostics_db_probe_failure(self, mcp_core, monkeypatch):
        # db_ok=False legs: the probe is the *first* count in health mode and
        # the *second* in full mode (the unguarded total read comes first).
        calls = {"n": 0}
        real_count = mcp_core.storage.count_entries

        def _flaky_count():
            calls["n"] += 1
            if calls["n"] == fail_on["call"]:
                raise OSError("db gone")
            return real_count()

        fail_on = {"call": 1}
        monkeypatch.setattr(mcp_core.storage, "count_entries", _flaky_count)
        health = await mcp_server.get_diagnostics(mode="health")
        assert health["db_ok"] is False

        calls["n"] = 0
        fail_on["call"] = 2
        full = await mcp_server.get_diagnostics(mode="full")
        assert full["health"]["db_ok"] is False

    async def test_diagnostics_error_leg(self, mcp_core, monkeypatch):
        monkeypatch.setattr(
            mcp_core.storage, "count_entries",
            lambda: (_ for _ in ()).throw(RuntimeError("dead")))
        # summary handler dies -> is_error result
        result = await mcp_server.get_diagnostics(mode="summary")
        assert result.is_error is True

        # MCPError is not a health-probe failure mode — it propagates.
        monkeypatch.setattr(
            mcp_core.storage, "count_entries",
            lambda: (_ for _ in ()).throw(MCPError(code=-32000, message="proto")))
        with pytest.raises(MCPError):
            await mcp_server.get_diagnostics(mode="health")

    async def test_add_entry_success_and_reraise(self, mcp_core, monkeypatch):
        result = await mcp_server.add_entry(ip="6.6.6.6")
        assert result == {"success": True}
        assert mcp_core.storage.is_ip_blacklisted("6.6.6.6") is True

        monkeypatch.setattr(
            mcp_core.storage, "add_entries",
            lambda *a: (_ for _ in ()).throw(MCPError(code=-32000, message="proto")))
        with pytest.raises(MCPError):
            await mcp_server.add_entry(url="http://e.com")

    async def test_remove_entry_result_and_errors(self, mcp_core, monkeypatch):
        result = await mcp_server.remove_entry("evil.com")
        assert result == {"success": True}
        assert await mcp_server.remove_entry("absent.com") == {"success": False}

        monkeypatch.setattr(
            mcp_core.storage, "remove_entry",
            lambda v: (_ for _ in ()).throw(ValueError("bad")))
        result = await mcp_server.remove_entry("x")
        assert result.is_error is True

        monkeypatch.setattr(
            mcp_core.storage, "remove_entry",
            lambda v: (_ for _ in ()).throw(MCPError(code=-32000, message="proto")))
        with pytest.raises(MCPError):
            await mcp_server.remove_entry("x")


# ============================================================================
# SecMCP facade — remaining check/status branches
# ============================================================================

class TestSecMCPBranches:
    @pytest.fixture
    def core(self, tmp_path):
        c = SecMCP(str(tmp_path / "core.db"))
        c.storage.add_domain("evil.com", "2025-01-01", 9.0, "FeedA")
        c.storage.add_url("http://phish.com/login", "2025-01-01", 8.0, "FeedB")
        c.storage.add_ip("4.4.4.4", "2025-01-01", 8.0, "FeedA")
        return c

    def test_check_all_value_types(self, core):
        assert core.check("4.4.4.4").blacklisted is True            # ip hit
        assert core.check("8.8.8.8").blacklisted is False           # ip miss
        assert core.check("http://phish.com/login").blacklisted is True   # url hit
        assert core.check("http://evil.com/landing").blacklisted is True  # via domain
        assert core.check("http://clean.com/x").blacklisted is False      # url miss
        assert core.check("evil.com").blacklisted is True           # domain hit
        assert core.check("clean.com").blacklisted is False         # domain miss
        assert core.check("not a value!!!").blacklisted is False    # invalid leg
        assert core.check("not a value!!!").explanation == "Invalid input type"

    def test_check_domain_url_ip(self, core):
        assert core.check_domain("sub.evil.com").blacklisted is True
        assert core.check_domain("clean.com").blacklisted is False
        assert core.check_url("http://phish.com/login").blacklisted is True
        assert core.check_url("http://evil.com/any").blacklisted is True   # domain leg
        assert core.check_url("http://clean.com/x").blacklisted is False
        assert core.check_ip("4.4.4.4").blacklisted is True
        assert core.check_ip("8.8.8.8").blacklisted is False

    def test_check_batch(self, core):
        results = core.check_batch(["evil.com", "4.4.4.4", "clean.com"])
        assert [r.blacklisted for r in results] == [True, True, False]

    def test_static_classifiers(self):
        assert SecMCP.is_url("HTTP://x.com") is True
        assert SecMCP.is_url("x.com") is False
        assert SecMCP.is_ip("2001:db8::1") is True
        assert SecMCP.is_ip("nope") is False
        assert SecMCP.is_domain("1.2.3.4") is False     # ip -> not domain
        assert SecMCP.is_domain("http://x.com") is False  # url -> not domain
        assert SecMCP.is_domain("nodot") is False
        assert SecMCP.is_domain("endswith.dot.") is False
        assert SecMCP.is_domain("ok.com") is True
        assert SecMCP.extract_domain("http://e.com:8080/p?q=1") == "e.com"
        assert SecMCP.extract_domain("http://localhost/") is None  # no dot

    def test_status_sample_scheduler(self, core):
        status = core.get_status()
        assert status.entry_count == 3
        data = status.to_dict()
        assert data["server_status"] == "Running (STDIO)"
        assert isinstance(data["last_update"], str)

        assert core.scheduler_alive() is False
        assert 1 <= len(core.sample(5)) <= 5

    def test_update_delegates_to_updater(self, core, monkeypatch):
        monkeypatch.setattr(core.updater, "force_update", lambda: {"updated": True})
        assert core.update() == {"updated": True}


# ============================================================================
# start_server entrypoint
# ============================================================================

def test_start_server_main(monkeypatch):
    calls = {}
    monkeypatch.setattr(start_server, "setup_logging", lambda level: calls.setdefault("log", level))
    monkeypatch.setattr(start_server, "get_core", lambda: calls.setdefault("core", True))
    monkeypatch.setattr(
        start_server.mcp, "run",
        lambda transport: calls.setdefault("transport", transport))
    start_server.main([])
    assert calls == {"log": "INFO", "core": True, "transport": "stdio"}
