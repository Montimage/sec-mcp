import sqlite3
from datetime import datetime
from typing import List, Optional, Set, Tuple
import threading
import random

class Storage:
    """SQLite-based storage with in-memory caching for high-throughput blacklist checks."""
    
    def __init__(self, db_path: str = "mcp.db"):
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
