"""Lookup-cost regression tests for the v1 storage backend (issue #57).

The legacy ``Storage`` used to pay one ``sqlite3.connect`` per storage call —
and one per parent-domain level inside a single lookup — plus a full-table
SELECT over every CIDR row on each IP check, an unbounded positive-hit
cache, and schema indexes duplicating the tables' PRIMARY KEYs.

These tests pin the new costs:

- exactly one connection per ``SecMCP.check()``;
- zero full-table CIDR scans per lookup (ranges are matched in memory);
- the positive-hit cache honours the configured max size;
- the schema carries no index duplicating a PRIMARY KEY.

``pytest -k "lookup_cost or cache_bound"`` selects this whole file.
"""

import ipaddress
import sqlite3
import threading

from sec_mcp.sec_mcp import SecMCP
from sec_mcp.storage import Storage
from sec_mcp.utility import load_config


class _ConnectSpy:
    """Wraps ``sqlite3.connect``: counts connections and traces their SQL.

    Every connection the spied code opens gets a trace callback, so
    ``statements`` records each SQL string as it executes — on the ambient
    shared connection and on standalone ones alike.
    """

    def __init__(self, monkeypatch):
        self.connects = 0
        self.statements = []
        real_connect = sqlite3.connect

        def spy(*args, **kwargs):
            self.connects += 1
            conn = real_connect(*args, **kwargs)
            conn.set_trace_callback(self.statements.append)
            return conn

        monkeypatch.setattr(sqlite3, "connect", spy)


def _core_with(storage):
    """A SecMCP bound to ``storage`` — no updater/scheduler side effects."""
    core = SecMCP.__new__(SecMCP)
    core.storage = storage
    return core


def _cidr_table_scans(statements):
    """Statements that read CIDR rows out of blacklist_ip.

    The trace callback expands bound parameters, so the exact-match lookups
    appear as ``WHERE ip = '...'``; anything else touching the table is a
    scan (the legacy code's ``WHERE INSTR(ip, '/') > 0`` shape).
    """
    return [
        s for s in statements
        if "from blacklist_ip" in s.lower() and "where ip = " not in s.lower()
    ]


def test_lookup_cost_one_connection_per_check(tmp_path, monkeypatch):
    """One SecMCP.check() pays exactly one sqlite3.connect, whatever it calls."""
    storage = Storage(str(tmp_path / "lookup_cost.db"))
    storage.add_domain("evil.com", "2025-01-01", 9.0, "TestSource")
    storage.add_url("http://bad.example.com/login", "2025-01-01", 8.5, "TestSource")
    storage.add_ip("203.0.113.9", "2025-01-01", 7.0, "TestSource")
    storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "TestSource")
    core = _core_with(storage)
    spy = _ConnectSpy(monkeypatch)

    cases = [
        "evil.com",                     # domain hit
        "deep.sub.evil.com",            # multi-level parent-domain hit
        "safe.example.org",             # domain miss
        "http://bad.example.com/login", # url hit
        "http://deep.sub.evil.com/x",   # url miss -> domain hit
        "203.0.113.9",                  # exact ip hit
        "10.1.2.3",                     # cidr member hit
        "198.51.100.4",                 # ip miss
    ]
    for value in cases:
        spy.connects = 0
        core.check(value)
        assert spy.connects == 1, f"{value}: {spy.connects} connections, want 1"


def test_lookup_cost_no_full_table_cidr_scan_per_lookup(tmp_path, monkeypatch):
    """Steady-state IP lookups run zero scans over the CIDR rows."""
    storage = Storage(str(tmp_path / "cidr_cost.db"))
    storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "SpamhausDROP")
    storage.add_ip("192.168.0.0/16", "2025-01-01", 8.0, "SpamhausDROP")
    storage.add_ip("203.0.113.9", "2025-01-01", 7.0, "BlocklistDE")

    # Warm the in-memory CIDR matcher — the one range load this backend pays.
    assert storage.is_ip_blacklisted("10.1.2.3") is True
    spy = _ConnectSpy(monkeypatch)
    core = _core_with(storage)

    # Raw lookups on fresh member IPs: exact-row probe runs, no CIDR scan.
    spy.statements.clear()
    assert storage.is_ip_blacklisted("10.9.8.7") is True
    assert storage.get_ip_blacklist_source("10.9.8.7") == "SpamhausDROP"
    assert _cidr_table_scans(spy.statements) == []

    # The same holds through the check() path (fresh IP again).
    spy.statements.clear()
    assert core.check("192.168.5.5").blacklisted is True
    assert _cidr_table_scans(spy.statements) == []


def test_lookup_cost_cidr_cache_tracks_writes(tmp_path):
    """The cached CIDR ranges follow blacklist_ip writes, not stale state."""
    storage = Storage(str(tmp_path / "cidr_track.db"))

    assert storage.is_ip_blacklisted("10.1.2.3") is False
    storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "SpamhausDROP")
    assert storage.is_ip_blacklisted("10.1.2.3") is True
    assert storage.get_ip_blacklist_source("10.1.2.3") == "SpamhausDROP"

    assert storage.remove_entry("10.0.0.0/8") is True
    assert storage.is_ip_blacklisted("10.1.2.3") is False
    assert storage.get_ip_blacklist_source("10.1.2.3") is None


def test_lookup_cost_cidr_load_cannot_overwrite_invalidation(tmp_path, monkeypatch):
    """A range load in flight during a write can never store over the invalidation.

    The loader fetches its snapshot, a writer commits a new CIDR row and
    invalidates, then the loader stores: serialized under ``_cidr_lock``
    the store must be followed by the invalidation, so the new range still
    matches — before the fix the stale store persisted and the new CIDR's
    members missed the blacklist until the next write.
    """
    storage = Storage(str(tmp_path / "cidr_race.db"))
    storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "SrcA")

    loading = threading.Event()
    release = threading.Event()
    real_ip_network = ipaddress.ip_network

    def pausing_ip_network(*args, **kwargs):
        # Pause between the loader's fetch and its store — the window in
        # which a committed write's invalidation could be overwritten.
        loading.set()
        assert release.wait(5), "test did not release the loader"
        return real_ip_network(*args, **kwargs)

    monkeypatch.setattr(ipaddress, "ip_network", pausing_ip_network)

    loader_errors = []

    def load():
        try:
            storage._cidr_entries()
        except Exception as exc:  # surfaced below, not lost in the thread
            loader_errors.append(exc)

    loader = threading.Thread(target=load)
    loader.start()
    assert loading.wait(5), "loader never reached the range parse"

    # The writer commits the new row, then blocks on _cidr_lock — held by
    # the in-flight load — before its invalidation can run.
    writer = threading.Thread(
        target=storage.add_ip, args=("192.168.0.0/16", "2025-01-01", 8.0, "SrcB")
    )
    writer.start()
    release.set()
    loader.join(5)
    writer.join(5)
    assert not loader.is_alive() and not writer.is_alive()
    assert loader_errors == []

    # However the load and the invalidation interleaved, the new CIDR's
    # members are blacklisted — the stale snapshot could not win.
    assert storage.is_ip_blacklisted("192.168.5.5") is True
    assert storage.get_ip_blacklist_source("192.168.5.5") == "SrcB"


def test_lookup_cost_schema_has_no_pk_duplicate_indexes(tmp_path):
    """No CREATEd index re-indexes a column that is already the PRIMARY KEY."""
    storage = Storage(str(tmp_path / "schema.db"))
    conn = sqlite3.connect(storage.db_path)
    try:
        for table, pk in (
            ("blacklist_domain", "domain"),
            ("blacklist_url", "url"),
            ("blacklist_ip", "ip"),
            ("updates", "id"),
        ):
            for row in conn.execute(f"PRAGMA index_list({table})"):
                name = row[1]
                if name.startswith("sqlite_autoindex_"):
                    continue  # the PRIMARY KEY's own backing index
                cols = [r[2] for r in conn.execute(f"PRAGMA index_info({name})")]
                assert cols != [pk], f"{name} duplicates the {table} PRIMARY KEY"
    finally:
        conn.close()


def test_lookup_cost_legacy_duplicate_indexes_dropped(tmp_path):
    """init_db sheds the PK-duplicating indexes a pre-#57 database may carry."""
    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE blacklist_domain (domain TEXT PRIMARY KEY, date TEXT, score REAL, source TEXT)"
    )
    conn.execute(
        "CREATE INDEX idx_blacklist_domain ON blacklist_domain(domain)"
    )
    conn.commit()
    conn.close()

    Storage(db_path)  # init_db drops the legacy index idempotently

    conn = sqlite3.connect(db_path)
    try:
        names = {row[1] for row in conn.execute("PRAGMA index_list(blacklist_domain)")}
        assert "idx_blacklist_domain" not in names
    finally:
        conn.close()


def test_cache_bound_uses_configured_max_size(tmp_path):
    """The cache bound defaults to config.json's ``cache_size`` value."""
    storage = Storage(str(tmp_path / "cache_cfg.db"))
    assert storage._cache_max_size == int(load_config().get("cache_size", 10000))


def test_cache_bound_evicts_oldest_at_max_size(tmp_path):
    """Positive hits beyond the configured bound evict the oldest entries."""
    storage = Storage(str(tmp_path / "cache_bound.db"), cache_size=2)
    for i in range(5):
        domain = f"evil{i}.com"
        storage.add_domain(domain, "2025-01-01", 9.0, "TestSource")
        assert storage.is_domain_blacklisted(domain) is True

    with storage._cache_lock:
        cached = list(storage._cache)
    assert len(cached) <= 2
    assert "evil0.com" not in cached  # evicted as the oldest hit
    assert "evil4.com" in cached


def test_cache_bound_zero_disables_caching(tmp_path):
    """A configured bound of 0 keeps every lookup out of the cache."""
    storage = Storage(str(tmp_path / "cache_zero.db"), cache_size=0)
    storage.add_domain("evil.com", "2025-01-01", 9.0, "TestSource")
    assert storage.is_domain_blacklisted("evil.com") is True
    with storage._cache_lock:
        assert len(storage._cache) == 0
