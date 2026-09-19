"""SQLite persistence layer for HybridStorage (v0.4.0).

Every SQLite interaction the hybrid backend performs lives in this module —
connection handling, schema initialization, row/tuple conversion and
transactions. :class:`sec_mcp.storage_v2.HybridStorage` keeps the in-memory
indexes and lookup logic; :class:`SQLiteStore` is the only object that knows
a database exists.
"""

import sqlite3
from typing import Dict, Iterator, List, Optional, Tuple

try:
    from .storage_base import init_db
except ImportError:
    # Direct file load (e.g. benchmark.py's spec_from_file_location) has no
    # package context for a relative import.
    from sec_mcp.storage_base import init_db


class SQLiteStore:
    """Owns every SQLite call for one HybridStorage database path.

    Connections are opened fresh per operation — never cached or shared.
    That is deliberate: ``":memory:"`` hands each ``sqlite3.connect`` a
    distinct empty database, which is exactly what makes HybridStorage
    construction fail closed on it instead of silently starting empty.

    A HybridStorage and its reload scratch instance each hold their own
    store, so no connection state is ever shared between them.
    """

    def __init__(self, db_path: str):
        """Bind the store to a database path (no connection is opened yet)."""
        self.db_path = db_path

    def init_schema(self) -> None:
        """Apply the shared schema and PRAGMAs via ``storage_base.init_db``."""
        init_db(self.db_path)

    def connect(self) -> sqlite3.Connection:
        """Open a fresh connection — one per call, never pooled."""
        return sqlite3.connect(self.db_path, timeout=30.0)

    # ========== Row reads (load snapshot) ==========

    def iter_domain_rows(self) -> Iterator[Tuple[str, str, str, float]]:
        """Yield ``(domain, source, date, score)`` rows, lazily."""
        conn = self.connect()
        try:
            yield from conn.execute(
                "SELECT domain, source, date, score FROM blacklist_domain"
            )
        finally:
            conn.close()

    def iter_url_rows(self) -> Iterator[Tuple[str, str, str, float]]:
        """Yield ``(url, source, date, score)`` rows, lazily."""
        conn = self.connect()
        try:
            yield from conn.execute(
                "SELECT url, source, date, score FROM blacklist_url"
            )
        finally:
            conn.close()

    def iter_ip_rows(self) -> Iterator[Tuple[str, str, str, float]]:
        """Yield ``(ip, source, date, score)`` rows, lazily."""
        conn = self.connect()
        try:
            yield from conn.execute(
                "SELECT ip, source, date, score FROM blacklist_ip"
            )
        finally:
            conn.close()

    # ========== Single-row writes ==========

    def upsert_domain(self, domain: str, date: str, score: float, source: str) -> None:
        """Insert or replace one domain row."""
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                (domain, date, score, source),
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_url(self, url: str, date: str, score: float, source: str) -> None:
        """Insert or replace one URL row (callers pass the canonical form)."""
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                (url, date, score, source),
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_ip(self, ip: str, date: str, score: float, source: str) -> None:
        """Insert or replace one IP/CIDR row."""
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                (ip, date, score, source),
            )
            conn.commit()
        finally:
            conn.close()

    # ========== Batch writes ==========

    def upsert_domains(self, rows: List[Tuple[str, str, float, str]]) -> None:
        """Insert or replace many ``(domain, date, score, source)`` rows in one transaction."""
        conn = self.connect()
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_urls(self, rows: List[Tuple[str, str, float, str]]) -> None:
        """Insert or replace many ``(url, date, score, source)`` rows in one transaction."""
        conn = self.connect()
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_ips(self, rows: List[Tuple[str, str, float, str]]) -> None:
        """Insert or replace many ``(ip, date, score, source)`` rows in one transaction."""
        conn = self.connect()
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        finally:
            conn.close()

    # ========== Deletes ==========

    def delete_entry(self, value: str, url_normalized: str) -> None:
        """Delete an entry from every blacklist table in one transaction.

        ``blacklist_url`` holds canonical forms, so the URL delete uses the
        normalized value. The domain delete matches case-insensitively:
        the memory side indexes domains lowercased, so removing "EVIL.COM"
        must also drop the stored "evil.com" row or it would resurrect on
        the next reload.
        """
        conn = self.connect()
        try:
            conn.execute("DELETE FROM blacklist_domain WHERE LOWER(domain) = ?", (value.lower(),))
            conn.execute("DELETE FROM blacklist_url WHERE url = ?", (url_normalized,))
            conn.execute("DELETE FROM blacklist_ip WHERE ip = ?", (value,))
            conn.commit()
        finally:
            conn.close()

    # ========== Update history ==========

    def get_last_update(self) -> Optional[str]:
        """Return the newest ``updates.timestamp`` value, or None."""
        conn = self.connect()
        try:
            return conn.execute("SELECT MAX(timestamp) FROM updates").fetchone()[0]
        finally:
            conn.close()

    def get_last_update_per_source(self) -> Dict[str, str]:
        """Return the newest ``updates.timestamp`` per source."""
        conn = self.connect()
        try:
            cursor = conn.execute(
                "SELECT source, MAX(timestamp) FROM updates GROUP BY source"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_update_history(
        self, source: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None
    ) -> List[Dict[str, object]]:
        """Return update-history records, newest filters applied in SQL."""
        conn = self.connect()
        try:
            parts = []
            params = []

            if source:
                parts.append("source = ?")
                params.append(source)
            if start:
                parts.append("timestamp >= ?")
                params.append(start)
            if end:
                parts.append("timestamp <= ?")
                params.append(end)

            query = "SELECT timestamp, source, entry_count FROM updates"
            if parts:
                query += " WHERE " + " AND ".join(parts)
            query += " ORDER BY timestamp"

            cursor = conn.execute(query, params)
            return [
                {"timestamp": row[0], "source": row[1], "entry_count": row[2]}
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def log_update(self, source: str, entry_count: int) -> None:
        """Append one row to the ``updates`` history table."""
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO updates (source, entry_count) VALUES (?, ?)",
                (source, entry_count),
            )
            conn.commit()
        finally:
            conn.close()
