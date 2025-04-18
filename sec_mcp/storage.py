import sqlite3
from datetime import datetime
from typing import List, Optional, Set, Tuple, Dict
import threading
import random
import os
import sys
from pathlib import Path

class Storage:
    """SQLite-based storage with in-memory caching for high-throughput blacklist checks."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.environ.get("MCP_DB_PATH")
        if db_path is None:
            try:
                from platformdirs import user_data_dir
                db_dir = user_data_dir("sec-mcp", "montimage")
            except ImportError:
                if os.name == "nt":
                    db_dir = os.path.join(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")), "sec-mcp")
                elif os.name == "posix":
                    if sys.platform == "darwin":
                        db_dir = str(Path.home() / "Library" / "Application Support" / "sec-mcp")
                    else:
                        db_dir = str(Path.home() / ".local" / "share" / "sec-mcp")
                else:
                    db_dir = str(Path.home() / ".sec-mcp")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "mcp.db")
        else:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._cache: Set[str] = set()  # In-memory cache for faster lookups
        self._cache_lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with required tables and performance PRAGMAs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA cache_size=10000;")
            # Recreate blacklist table with new schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    url TEXT,
                    ip TEXT,
                    date TEXT,
                    score REAL,
                    source TEXT,
                    UNIQUE(url)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_blacklist_url ON blacklist(url);
            """)
            # Create updates table (unchanged)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT NOT NULL,
                    entry_count INTEGER NOT NULL
                )
            """)
            conn.commit()

    def is_blacklisted(self, value: str) -> bool:
        """Check if a URL or IP is blacklisted using cache first, then database."""
        # In-memory cache check
        with self._cache_lock:
            if value in self._cache:
                return True
        # Database lookup by URL or IP
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM blacklist WHERE url = ? OR ip = ?",
                (value, value)
            )
            return cursor.fetchone() is not None

    def get_blacklist_source(self, value: str) -> Optional[str]:
        """Get the source that blacklisted a value."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT source FROM blacklist WHERE url = ? OR ip = ?",
                (value, value)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def add_entries(self, entries: List[Tuple[str, str, str, float, str]]):
        """Add multiple entries (url, ip, date, score, source) to the blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist (url, ip, date, score, source) VALUES (?, ?, ?, ?, ?)",
                entries
            )
            conn.commit()
        # Update cache with new URLs and IPs
        with self._cache_lock:
            for url, ip, *_ in entries:
                self._cache.add(url)
                if ip:
                    self._cache.add(ip)
            if len(self._cache) > 10000:
                self._cache.clear()

    def log_update(self, source: str, entry_count: int):
        """Log a successful update from a source."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO updates (source, entry_count) VALUES (?, ?)",
                (source, entry_count)
            )
            conn.commit()

    def count_entries(self) -> int:
        """Get total number of blacklist entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM blacklist")
            return cursor.fetchone()[0]

    def get_source_counts(self) -> Dict[str, int]:
        """Get the number of blacklist entries for each source."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT source, COUNT(*) FROM blacklist GROUP BY source")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_last_update(self) -> datetime:
        """Get timestamp of last update."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT MAX(timestamp) FROM updates"
            )
            result = cursor.fetchone()[0]
            return datetime.fromisoformat(result) if result else datetime.min

    def get_active_sources(self) -> List[str]:
        """Get list of active blacklist sources."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT source FROM blacklist"
            )
            return [row[0] for row in cursor.fetchall()]

    def sample_entries(self, count: int = 10) -> List[str]:
        """Return a random sample of blacklist entries for testing."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT url FROM blacklist ORDER BY RANDOM() LIMIT ?",
                (count,)
            )
            return [row[0] for row in cursor.fetchall()]

    def get_last_update_per_source(self) -> Dict[str, str]:
        """Get last update timestamp for each source."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT source, MAX(timestamp) FROM updates GROUP BY source"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_update_history(self, source: str = None, start: str = None, end: str = None) -> list:
        """Return update history records, optionally filtered by source and time range."""
        with sqlite3.connect(self.db_path) as conn:
            parts = []
            params = []
            if source:
                parts.append("source = ?") and params.append(source)
            if start:
                parts.append("timestamp >= ?") and params.append(start)
            if end:
                parts.append("timestamp <= ?") and params.append(end)
            query = "SELECT timestamp, source, entry_count FROM updates"
            if parts:
                query += " WHERE " + " AND ".join(parts)
            query += " ORDER BY timestamp"
            cursor = conn.execute(query, params)
            return [
                {"timestamp": row[0], "source": row[1], "entry_count": row[2]}
                for row in cursor.fetchall()
            ]

    def flush_cache(self) -> bool:
        """Clear the in-memory URL/IP cache."""
        with self._cache_lock:
            self._cache.clear()
        return True

    def remove_entry(self, value: str) -> bool:
        """Remove a blacklist entry by URL or IP."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM blacklist WHERE url = ? OR ip = ?",
                (value, value)
            )
            conn.commit()
        with self._cache_lock:
            self._cache.discard(value)
        return cursor.rowcount > 0
