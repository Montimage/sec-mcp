"""Unit tests for HybridStorage (v2)."""

import os
import sqlite3
import sys
import tempfile
import threading
import tracemalloc

import pytest

from sec_mcp.storage import create_storage
from sec_mcp.storage_v2 import HybridStorage


class TestHybridStorageInitialization:
    """Test storage initialization and setup."""

    def test_initialization_with_memory_db(self):
        """In-memory databases are unsupported: each connection gets a fresh
        empty DB, so initialization must fail closed instead of silently
        presenting an empty store."""
        with pytest.raises(RuntimeError):
            HybridStorage(":memory:")

    def test_initialization_with_file_db(self):
        """Test initialization with file database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            storage = HybridStorage(db_path)
            assert storage.db_path == db_path
            assert os.path.exists(db_path)

    def test_database_tables_created(self):
        """Test that all required tables are created."""
        storage = HybridStorage(":memory:")
        conn = sqlite3.connect(storage.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        assert "blacklist_domain" in tables
        assert "blacklist_url" in tables
        assert "blacklist_ip" in tables
        assert "updates" in tables

        conn.close()


class TestDomainLookups:
    """Test domain blacklist lookups."""

    def test_exact_domain_match(self):
        """Test exact domain match."""
        storage = HybridStorage(":memory:")
        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")

        assert storage.is_domain_blacklisted("evil.com") is True
        assert storage.is_domain_blacklisted("safe.com") is False

    def test_parent_domain_match(self):
        """Test parent domain matching."""
        storage = HybridStorage(":memory:")
        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")

        # Subdomains should match parent domain
        assert storage.is_domain_blacklisted("sub.evil.com") is True
        assert storage.is_domain_blacklisted("a.b.c.evil.com") is True

    def test_case_insensitive_domain(self):
        """Test case-insensitive domain matching."""
        storage = HybridStorage(":memory:")
        storage.add_domain("Evil.Com", "2025-01-01", 9.0, "test")

        assert storage.is_domain_blacklisted("evil.com") is True
        assert storage.is_domain_blacklisted("EVIL.COM") is True
        assert storage.is_domain_blacklisted("EviL.CoM") is True

    def test_domain_source_retrieval(self):
        """Test retrieving source of blacklisted domain."""
        storage = HybridStorage(":memory:")
        storage.add_domain("evil.com", "2025-01-01", 9.0, "TestSource")

        source = storage.get_domain_blacklist_source("evil.com")
        assert source == "TestSource"

        source = storage.get_domain_blacklist_source("sub.evil.com")
        assert source == "TestSource"

        source = storage.get_domain_blacklist_source("safe.com")
        assert source is None


class TestURLLookups:
    """Test URL blacklist lookups."""

    def test_exact_url_match(self):
        """Test exact URL matching."""
        storage = HybridStorage(":memory:")
        storage.add_url("http://example.com/malware", "2025-01-01", 8.5, "test")

        assert storage.is_url_blacklisted("http://example.com/malware") is True
        assert storage.is_url_blacklisted("http://example.com/safe") is False
        assert storage.is_url_blacklisted("http://example.com") is False

    def test_url_source_retrieval(self):
        """Test retrieving source of blacklisted URL."""
        storage = HybridStorage(":memory:")
        storage.add_url("http://phishing.example.com/login", "2025-01-01", 9.0, "PhishTank")

        source = storage.get_url_blacklist_source("http://phishing.example.com/login")
        assert source == "PhishTank"

        source = storage.get_url_blacklist_source("http://safe.com")
        assert source is None


class TestIPLookups:
    """Test IP blacklist lookups."""

    def test_exact_ip_match(self):
        """Test exact IP matching."""
        storage = HybridStorage(":memory:")
        storage.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")

        assert storage.is_ip_blacklisted("192.168.1.100") is True
        assert storage.is_ip_blacklisted("192.168.1.101") is False

    def test_cidr_range_match(self):
        """Test CIDR range matching."""
        storage = HybridStorage(":memory:")
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")

        # IPs in the range should match
        assert storage.is_ip_blacklisted("10.0.0.1") is True
        assert storage.is_ip_blacklisted("10.255.255.255") is True

        # IPs outside the range should not match
        assert storage.is_ip_blacklisted("11.0.0.1") is False
        assert storage.is_ip_blacklisted("192.168.1.1") is False

    def test_ipv6_support(self):
        """Test IPv6 address support."""
        storage = HybridStorage(":memory:")
        storage.add_ip("2001:db8::1", "2025-01-01", 8.0, "test")

        assert storage.is_ip_blacklisted("2001:db8::1") is True
        assert storage.is_ip_blacklisted("2001:db8::2") is False

    def test_ip_source_retrieval(self):
        """Test retrieving source of blacklisted IP."""
        storage = HybridStorage(":memory:")
        storage.add_ip("203.0.113.42", "2025-01-01", 9.0, "SpamhausDROP")

        source = storage.get_ip_blacklist_source("203.0.113.42")
        assert source == "SpamhausDROP"

        source = storage.get_ip_blacklist_source("198.51.100.1")
        assert source is None


class TestBatchOperations:
    """Test batch write operations."""

    def test_add_domains_batch(self):
        """Test adding multiple domains at once."""
        storage = HybridStorage(":memory:")

        domains = [
            ("evil1.com", "2025-01-01", 9.0, "test"),
            ("evil2.com", "2025-01-01", 8.5, "test"),
            ("evil3.com", "2025-01-01", 9.5, "test"),
        ]

        storage.add_domains(domains)

        assert storage.is_domain_blacklisted("evil1.com") is True
        assert storage.is_domain_blacklisted("evil2.com") is True
        assert storage.is_domain_blacklisted("evil3.com") is True
        assert storage.count_entries() == 3

    def test_add_urls_batch(self):
        """Test adding multiple URLs at once."""
        storage = HybridStorage(":memory:")

        urls = [
            ("http://phishing1.com/login", "2025-01-01", 9.0, "test"),
            ("http://phishing2.com/login", "2025-01-01", 8.5, "test"),
        ]

        storage.add_urls(urls)

        assert storage.is_url_blacklisted("http://phishing1.com/login") is True
        assert storage.is_url_blacklisted("http://phishing2.com/login") is True
        assert storage.count_entries() == 2

    def test_add_ips_batch(self):
        """Test adding multiple IPs at once."""
        storage = HybridStorage(":memory:")

        ips = [
            ("192.168.1.1", "2025-01-01", 7.0, "test"),
            ("10.0.0.0/8", "2025-01-01", 8.0, "test"),
            ("203.0.113.0/24", "2025-01-01", 9.0, "test"),
        ]

        storage.add_ips(ips)

        assert storage.is_ip_blacklisted("192.168.1.1") is True
        assert storage.is_ip_blacklisted("10.5.5.5") is True  # In CIDR range
        assert storage.is_ip_blacklisted("203.0.113.50") is True  # In CIDR range


class TestStatistics:
    """Test statistics and counting methods."""

    def test_count_entries(self):
        """Test total entry count."""
        storage = HybridStorage(":memory:")

        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")
        storage.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")

        assert storage.count_entries() == 3

    def test_get_source_counts(self):
        """Test getting counts per source."""
        storage = HybridStorage(":memory:")

        storage.add_domain("evil1.com", "2025-01-01", 9.0, "Source1")
        storage.add_domain("evil2.com", "2025-01-01", 9.0, "Source1")
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "Source2")
        storage.add_ip("192.168.1.100", "2025-01-01", 7.0, "Source1")

        counts = storage.get_source_counts()

        assert counts["Source1"] == 3  # 2 domains + 1 IP
        assert counts["Source2"] == 1  # 1 URL

    def test_get_active_sources(self):
        """Test getting list of active sources."""
        storage = HybridStorage(":memory:")

        storage.add_domain("evil.com", "2025-01-01", 9.0, "OpenPhish")
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "PhishTank")

        sources = storage.get_active_sources()

        assert "OpenPhish" in sources
        assert "PhishTank" in sources
        assert len(sources) == 2

    def test_sample_entries(self):
        """Test sampling random entries."""
        storage = HybridStorage(":memory:")

        # Add some entries
        for i in range(20):
            storage.add_domain(f"evil{i}.com", "2025-01-01", 9.0, "test")

        sample = storage.sample_entries(10)

        assert len(sample) == 10
        assert all(entry.startswith("evil") and entry.endswith(".com") for entry in sample)


class TestPersistence:
    """Test data persistence between sessions."""

    def test_data_persists_between_instances(self):
        """Test that data persists in database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Create first instance and add data
            storage1 = HybridStorage(db_path)
            storage1.add_domain("evil.com", "2025-01-01", 9.0, "test")
            storage1.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")
            storage1.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")

            del storage1  # Destroy first instance

            # Create second instance and verify data loaded
            storage2 = HybridStorage(db_path)

            assert storage2.is_domain_blacklisted("evil.com") is True
            assert storage2.is_url_blacklisted("http://phishing.com/login") is True
            assert storage2.is_ip_blacklisted("192.168.1.100") is True
            assert storage2.count_entries() == 3


class TestRemoval:
    """Test entry removal."""

    def test_remove_domain(self):
        """Test removing a domain."""
        storage = HybridStorage(":memory:")
        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")

        assert storage.is_domain_blacklisted("evil.com") is True

        success = storage.remove_entry("evil.com")
        assert success is True
        assert storage.is_domain_blacklisted("evil.com") is False

    def test_remove_url(self):
        """Test removing a URL."""
        storage = HybridStorage(":memory:")
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")

        assert storage.is_url_blacklisted("http://phishing.com/login") is True

        success = storage.remove_entry("http://phishing.com/login")
        assert success is True
        assert storage.is_url_blacklisted("http://phishing.com/login") is False

    def test_remove_ip(self):
        """Test removing an IP."""
        storage = HybridStorage(":memory:")
        storage.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")

        assert storage.is_ip_blacklisted("192.168.1.100") is True

        success = storage.remove_entry("192.168.1.100")
        assert success is True
        assert storage.is_ip_blacklisted("192.168.1.100") is False


class TestReload:
    """Test data reloading."""

    def test_reload_updates_memory(self):
        """Test that reload updates in-memory data from database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            storage = HybridStorage(db_path)

            # Add data directly to database (bypassing memory)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                ("evil.com", "2025-01-01", 9.0, "test")
            )
            conn.commit()
            conn.close()

            # Before reload, memory doesn't have it
            assert "evil.com" not in storage._domains

            # Reload
            storage.reload()

            # After reload, memory should have it
            assert "evil.com" in storage._domains
            assert storage.is_domain_blacklisted("evil.com") is True


class TestMetrics:
    """Test performance metrics tracking."""

    def test_metrics_tracking(self):
        """Test that metrics are tracked correctly."""
        storage = HybridStorage(":memory:")
        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")

        # Perform some lookups
        storage.is_domain_blacklisted("evil.com")
        storage.is_domain_blacklisted("safe.com")
        storage.is_url_blacklisted("http://example.com")

        metrics = storage.get_metrics()

        assert metrics["total_lookups"] == 3
        assert metrics["domain_lookups"] == 2
        assert metrics["url_lookups"] == 1
        assert metrics["cache_hits"] == 1  # evil.com was found
        assert metrics["cache_misses"] == 2  # safe.com and url not found
        assert float(metrics["avg_lookup_time_ms"]) >= 0


class TestUpdateHistory:
    """Test update history tracking."""

    def test_log_update(self):
        """Test logging updates."""
        storage = HybridStorage(":memory:")

        storage.log_update("OpenPhish", 1000)
        storage.log_update("PhishTank", 2000)

        history = storage.get_update_history()

        assert len(history) == 2
        assert history[0]["source"] == "OpenPhish"
        assert history[0]["entry_count"] == 1000
        assert history[1]["source"] == "PhishTank"
        assert history[1]["entry_count"] == 2000

    def test_filtered_update_history(self):
        """Test filtering update history."""
        storage = HybridStorage(":memory:")

        storage.log_update("OpenPhish", 1000)
        storage.log_update("PhishTank", 2000)
        storage.log_update("OpenPhish", 1100)

        # Filter by source
        history = storage.get_update_history(source="OpenPhish")
        assert len(history) == 2
        assert all(h["source"] == "OpenPhish" for h in history)


def test_sample_entries_bounded_allocation(tmp_path):
    """sample_entries(10) must not materialize a list of all entries.

    Seeds a 100K-entry store via a single bulk transaction, then asserts the
    peak allocation during the call stays far below what a full-entry list
    would cost (~1.8MB of pointers alone for 100K entries).
    """
    storage = HybridStorage(str(tmp_path / "big.db"))
    storage.add_domains(
        [(f"evil{i}.com", "2025-01-01", 9.0, "test") for i in range(100_000)]
    )
    assert storage.count_entries() == 100_000

    tracemalloc.start()
    try:
        sample = storage.sample_entries(10)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert len(sample) == 10
    assert len(set(sample)) == 10
    assert all(entry in storage._domains for entry in sample)
    # Reservoir sampling uses O(count) space; a full-entry list would
    # exceed this bound many times over.
    assert peak < 1_000_000


def test_sample_entries_small_store_and_zero_count(tmp_path):
    """Edge cases: empty store, count above size, and non-positive count."""
    storage = HybridStorage(str(tmp_path / "small.db"))
    assert storage.sample_entries(10) == []

    storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
    assert storage.sample_entries(0) == []
    assert storage.sample_entries(10) == ["evil.com"]


def test_fail_closed_corrupt_db(tmp_path):
    """A corrupt database raises instead of silently starting empty."""
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"not a sqlite database" * 64)
    with pytest.raises(RuntimeError):
        HybridStorage(str(db))


def test_fail_closed_unreadable_db_path(tmp_path):
    """A database path that cannot be opened raises instead of an empty store."""
    with pytest.raises(RuntimeError):
        HybridStorage(str(tmp_path))

    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory")
    with pytest.raises(RuntimeError):
        HybridStorage(str(blocker / "nested" / "test.db"))


def test_fail_closed_schema_init_failure(tmp_path, monkeypatch):
    """A schema/init failure inside HybridStorage propagates, not an empty store."""
    def _boom(self):
        raise sqlite3.OperationalError("cannot create tables")
    monkeypatch.setattr(HybridStorage, "_init_db", _boom)
    with pytest.raises(RuntimeError):
        HybridStorage(str(tmp_path / "schema.db"))


def test_fail_closed_no_silent_v1_fallback(tmp_path, monkeypatch):
    """With v2 explicitly selected, create_storage propagates instead of falling back to v1."""
    monkeypatch.setenv("MCP_USE_V2_STORAGE", "true")
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"not a sqlite database" * 64)
    with pytest.raises(RuntimeError):
        create_storage(str(db))


class TestV2StateConsistency:
    """Issue #49 — v2 state consistency acceptance tests.

    All selected by ``-k "v2 and (count or cidr or reload)"``.
    """

    def test_v2_count_entries_equals_db_row_count(self, tmp_path):
        """count_entries() reports exactly the rows persisted in SQLite."""
        storage = HybridStorage(str(tmp_path / "count.db"))

        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")
        storage.add_ip("192.0.2.1", "2025-01-01", 7.0, "test")
        storage.add_ip("2001:db8::1", "2025-01-01", 7.0, "test")
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")

        conn = sqlite3.connect(storage.db_path)
        try:
            db_rows = sum(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("blacklist_domain", "blacklist_url", "blacklist_ip")
            )
        finally:
            conn.close()

        assert storage.count_entries() == db_rows == 5

    def test_v2_count_unchanged_when_invalid_ip_rejected(self, tmp_path):
        """add_ip rejects an out-of-range octet instead of storing a bogus int."""
        storage = HybridStorage(str(tmp_path / "reject.db"))

        with pytest.raises(ValueError):
            storage.add_ip("1.2.3.999", "2025-01-01", 9.0, "test")

        assert storage.count_entries() == 0
        assert storage.is_ip_blacklisted("1.2.3.999") is False

    def test_v2_cidr_lookup_rejects_malformed_ip(self, tmp_path):
        """An out-of-range octet must not alias a real, different address.

        ``1.2.3.999`` used to overflow into ``1.2.6.231`` inside
        ``ip_to_int`` — matching that host — and unparseable input crashed
        the radix-tree lookup (pytricia raises SystemError on bad keys).
        """
        storage = HybridStorage(str(tmp_path / "alias.db"))
        storage.add_ip("1.2.6.231", "2025-01-01", 9.0, "test")

        assert storage.is_ip_blacklisted("1.2.3.999") is False
        assert storage.get_ip_blacklist_source("1.2.3.999") is None

    def test_v2_cidr_lookup_rejects_noncanonical_ipv4(self, tmp_path):
        """Non-canonical octets int() accepts must not alias or crash.

        ``int("+1")``, ``int(" 1")`` and ``int("01")`` all succeed, so
        ``+1.2.3.4``, ``" 1.2.3.4"`` and ``1.2.3.04`` used to map onto the
        ``1.2.3.4`` integer — aliasing that entry — and ``+1.2.3.4``
        reached the radix tree, where pytricia raises SystemError.
        """
        storage = HybridStorage(str(tmp_path / "noncanonical.db"))
        storage.add_ip("1.2.3.4", "2025-01-01", 9.0, "test")

        for malformed in ("+1.2.3.4", " 1.2.3.4", "1.2.3.4 ", "1.2.3.04"):
            assert storage.is_ip_blacklisted(malformed) is False
            assert storage.get_ip_blacklist_source(malformed) is None

        storage.add_ips([
            ("+1.2.3.4", "2025-01-01", 9.0, "test"),
            ("1.2.3.04", "2025-01-01", 9.0, "test"),
        ])
        assert storage.count_entries() == 1

    @pytest.mark.parametrize("use_pytricia", [True, False], ids=["pytricia", "fallback"])
    def test_v2_cidr_removal_stops_matching_without_reload(
        self, tmp_path, monkeypatch, use_pytricia
    ):
        """remove_entry evicts the CIDR from the live matcher immediately."""
        if not use_pytricia:
            # Force the _cidr_ranges fallback path even where pytricia exists.
            monkeypatch.setitem(sys.modules, "pytricia", None)
        storage = HybridStorage(str(tmp_path / "cidr.db"))
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")

        assert storage.is_ip_blacklisted("10.1.2.3") is True

        assert storage.remove_entry("10.0.0.0/8") is True
        assert storage.is_ip_blacklisted("10.1.2.3") is False
        assert storage.get_ip_blacklist_source("10.1.2.3") is None

    @pytest.mark.parametrize("use_pytricia", [True, False], ids=["pytricia", "fallback"])
    def test_v2_cidr_add_ip_rollback_drops_matcher_entry(
        self, tmp_path, monkeypatch, use_pytricia
    ):
        """A failed DB write must roll the CIDR out of the live matcher too.

        Regression test: the rollback path dropped only the range's
        metadata, leaving the radix-tree (or fallback-list) entry matching
        member IPs — a phantom blacklist hit surviving until the next reload.
        """
        if not use_pytricia:
            # Force the _cidr_ranges fallback path even where pytricia exists.
            monkeypatch.setitem(sys.modules, "pytricia", None)
        storage = HybridStorage(str(tmp_path / "rollback.db"))

        def _fail(*args, **kwargs):
            raise sqlite3.OperationalError("disk full")

        monkeypatch.setattr(storage._db, "upsert_ip", _fail)

        with pytest.raises(sqlite3.OperationalError):
            storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")

        assert storage.is_ip_blacklisted("10.1.2.3") is False
        assert storage.get_ip_blacklist_source("10.1.2.3") is None

    def test_v2_reload_lookup_never_returns_false_for_present_entry(self, tmp_path):
        """Concurrent lookups observe a complete snapshot during reload().

        Regression test: reload used to clear every in-memory structure and
        refill it in place, so a racing lookup saw an empty table and
        reported a blacklisted entry as clean.
        """
        storage = HybridStorage(str(tmp_path / "reload.db"))
        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
        storage.add_ip("192.0.2.1", "2025-01-01", 7.0, "test")

        misses = []
        stop = threading.Event()

        def reader():
            while not stop.is_set():
                if not storage.is_domain_blacklisted("evil.com"):
                    misses.append("domain")
                if not storage.is_ip_blacklisted("192.0.2.1"):
                    misses.append("ip")

        readers = [threading.Thread(target=reader) for _ in range(4)]
        for thread in readers:
            thread.start()
        try:
            for _ in range(20):
                storage.reload()
        finally:
            stop.set()
            for thread in readers:
                thread.join()

        assert misses == []
        assert storage.is_domain_blacklisted("evil.com") is True
        assert storage.is_ip_blacklisted("192.0.2.1") is True
        assert storage.count_entries() == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
