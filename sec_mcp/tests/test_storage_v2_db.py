"""Unit tests for SQLiteStore — the v2 persistence layer (issue #52)."""

import sqlite3
from pathlib import Path

import pytest

import sec_mcp.storage_v2
from sec_mcp.storage_v2 import HybridStorage
from sec_mcp.storage_v2_db import SQLiteStore


@pytest.fixture
def store(tmp_path):
    """A schema-initialized store on a fresh file-backed database."""
    db = SQLiteStore(str(tmp_path / "store.db"))
    db.init_schema()
    return db


def _rows(db_path, sql):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


class TestSchema:
    def test_init_schema_creates_tables(self, tmp_path):
        db_path = str(tmp_path / "schema.db")
        SQLiteStore(db_path).init_schema()

        tables = {
            row[0]
            for row in _rows(
                db_path, "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"blacklist_domain", "blacklist_url", "blacklist_ip", "updates"} <= tables

    def test_connect_uses_database_path(self, tmp_path):
        db_path = str(tmp_path / "conn.db")
        store = SQLiteStore(db_path)
        assert store.db_path == db_path
        conn = store.connect()
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()

    def test_init_schema_marks_canonicalization_done(self, tmp_path):
        """init_db stamps ``PRAGMA user_version`` so re-opens skip the URL rescan."""
        db_path = str(tmp_path / "versioned.db")
        SQLiteStore(db_path).init_schema()

        (version,) = _rows(db_path, "PRAGMA user_version")[0]
        assert version >= 1


class TestRowReadsAndWrites:
    def test_domain_roundtrip(self, store):
        store.upsert_domain("evil.com", "2025-01-01", 9.0, "test")
        assert list(store.iter_domain_rows()) == [
            ("evil.com", "test", "2025-01-01", 9.0)
        ]

    def test_url_roundtrip(self, store):
        store.upsert_url("http://evil.com/x", "2025-01-01", 8.5, "test")
        assert list(store.iter_url_rows()) == [
            ("http://evil.com/x", "test", "2025-01-01", 8.5)
        ]

    def test_ip_roundtrip(self, store):
        store.upsert_ip("192.0.2.1", "2025-01-01", 7.0, "test")
        store.upsert_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")
        assert list(store.iter_ip_rows()) == [
            ("192.0.2.1", "test", "2025-01-01", 7.0),
            ("10.0.0.0/8", "test", "2025-01-01", 8.0),
        ]

    def test_upsert_replaces_existing_row(self, store):
        store.upsert_domain("evil.com", "2025-01-01", 9.0, "old")
        store.upsert_domain("evil.com", "2025-01-02", 5.0, "new")
        assert list(store.iter_domain_rows()) == [
            ("evil.com", "new", "2025-01-02", 5.0)
        ]

    def test_batch_upserts(self, store):
        store.upsert_domains(
            [("a.com", "2025-01-01", 9.0, "s"), ("b.com", "2025-01-01", 8.0, "s")]
        )
        store.upsert_urls([("http://a.com/x", "2025-01-01", 9.0, "s")])
        store.upsert_ips(
            [("192.0.2.1", "2025-01-01", 7.0, "s"), ("10.0.0.0/8", "2025-01-01", 8.0, "s")]
        )

        assert len(list(store.iter_domain_rows())) == 2
        assert len(list(store.iter_url_rows())) == 1
        assert len(list(store.iter_ip_rows())) == 2


class TestDeleteEntry:
    def test_delete_entry_removes_from_all_tables(self, store):
        store.upsert_domain("evil.com", "2025-01-01", 9.0, "test")
        store.upsert_url("http://evil.com/x", "2025-01-01", 8.5, "test")
        store.upsert_ip("192.0.2.1", "2025-01-01", 7.0, "test")

        store.delete_entry("evil.com", "http://evil.com")
        store.delete_entry("192.0.2.1", "192.0.2.1")

        assert list(store.iter_domain_rows()) == []
        assert list(store.iter_ip_rows()) == []
        # The URL delete used the normalized value — the raw row survives,
        # matching HybridStorage.remove_entry semantics.
        assert list(store.iter_url_rows()) == [
            ("http://evil.com/x", "test", "2025-01-01", 8.5)
        ]

    def test_delete_entry_domain_case_insensitive(self, store):
        """The domain delete matches the stored row regardless of caller case."""
        store.upsert_domain("evil.com", "2025-01-01", 9.0, "test")

        store.delete_entry("EVIL.COM", "http://evil.com")

        assert list(store.iter_domain_rows()) == []

    def test_delete_entry_removes_canonical_url(self, store):
        store.upsert_url("http://evil.com", "2025-01-01", 8.5, "test")
        store.delete_entry("evil.com", "http://evil.com")
        assert list(store.iter_url_rows()) == []


class TestUpdateHistory:
    def test_log_and_read_history(self, store):
        store.log_update("OpenPhish", 100)
        store.log_update("PhishTank", 200)

        history = store.get_update_history()
        assert len(history) == 2
        assert history[0]["source"] == "OpenPhish"
        assert history[0]["entry_count"] == 100
        assert history[1]["source"] == "PhishTank"

    def test_history_filters(self, store):
        store.log_update("OpenPhish", 100)
        store.log_update("PhishTank", 200)
        store.log_update("OpenPhish", 150)

        assert len(store.get_update_history(source="OpenPhish")) == 2
        assert store.get_update_history(source="NoSuch") == []
        assert len(store.get_update_history(start="1970-01-01", end="2999-01-01")) == 3
        assert store.get_update_history(start="2999-01-01") == []
        assert store.get_update_history(end="1970-01-01") == []

    def test_last_update(self, store):
        assert store.get_last_update() is None
        store.log_update("OpenPhish", 100)
        assert store.get_last_update() is not None
        assert store.get_last_update_per_source() == {
            "OpenPhish": store.get_last_update()
        }


class TestHybridStorageBoundary:
    """The split itself: HybridStorage holds a store, never a connection."""

    def test_storage_v2_module_has_no_sqlite_reference(self):
        """Acceptance pin: the HybridStorage module must not reference sqlite3."""
        source = Path(sec_mcp.storage_v2.__file__).read_text()
        assert "sqlite3" not in source

    def test_hybrid_storage_owns_a_store(self, tmp_path):
        storage = HybridStorage(str(tmp_path / "own.db"))
        assert isinstance(storage._db, SQLiteStore)
        assert storage._db.db_path == storage.db_path

    def test_scratch_gets_its_own_store(self, tmp_path):
        """The reload scratch shares no persistence state with the live instance."""
        storage = HybridStorage(str(tmp_path / "scratch.db"))
        scratch = storage._scratch()
        assert isinstance(scratch._db, SQLiteStore)
        assert scratch._db is not storage._db
        assert scratch._db.db_path == storage.db_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
