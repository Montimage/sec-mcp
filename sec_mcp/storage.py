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
            # Create new blacklist tables for domain, url, and ip
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist_domain (
                    domain TEXT PRIMARY KEY,
                    date TEXT,
                    score REAL,
                    source TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_blacklist_domain ON blacklist_domain(domain);
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist_url (
                    url TEXT PRIMARY KEY,
                    date TEXT,
                    score REAL,
                    source TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_blacklist_url ON blacklist_url(url);
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist_ip (
                    ip TEXT PRIMARY KEY,
                    date TEXT,
                    score REAL,
                    source TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_blacklist_ip ON blacklist_ip(ip);
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

    def is_domain_blacklisted(self, domain: str) -> bool:
        """Check if a domain or its parent domains are blacklisted."""
        # Check domain and all parent domains
        domain_parts = domain.lower().split('.')
        for i in range(len(domain_parts) - 1):
            sub = '.'.join(domain_parts[i:])
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM blacklist_domain WHERE domain = ?",
                    (sub,)
                )
                if cursor.fetchone():
                    return True
        return False

    def is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL is blacklisted (exact match)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM blacklist_url WHERE url = ?",
                (url,)
            )
            return cursor.fetchone() is not None

    def is_ip_blacklisted(self, ip: str) -> bool:
        """Check if an IP is blacklisted (either exact match or contained in any network mask)."""
        import ipaddress
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return False
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT ip FROM blacklist_ip")
            for (entry,) in cursor.fetchall():
                try:
                    # Try to parse as a network, fallback to exact IP
                    if '/' in entry:
                        net = ipaddress.ip_network(entry, strict=False)
                        if ip_obj in net:
                            return True
                    else:
                        if ip_obj == ipaddress.ip_address(entry):
                            return True
                except Exception:
                    continue
        return False

    def add_domain(self, domain: str, date: str, score: float, source: str):
        """Add a domain to the domain blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                (domain, date, score, source)
            )
            conn.commit()

    def add_url(self, url: str, date: str, score: float, source: str):
        """Add a URL to the URL blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                (url, date, score, source)
            )
            conn.commit()

    def add_ip(self, ip: str, date: str, score: float, source: str):
        """Add an IP to the IP blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                (ip, date, score, source)
            )
            conn.commit()

    def remove_domain(self, domain: str) -> bool:
        """Remove a domain from the domain blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM blacklist_domain WHERE domain = ?",
                (domain,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def remove_url(self, url: str) -> bool:
        """Remove a URL from the URL blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM blacklist_url WHERE url = ?",
                (url,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def remove_ip(self, ip: str) -> bool:
        """Remove an IP from the IP blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM blacklist_ip WHERE ip = ?",
                (ip,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def get_domain_blacklist_source(self, domain: str) -> Optional[str]:
        """Get the source that blacklisted a domain (including parent domains)."""
        domain_parts = domain.lower().split('.')
        for i in range(len(domain_parts) - 1):
            sub = '.'.join(domain_parts[i:])
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT source FROM blacklist_domain WHERE domain = ?",
                    (sub,)
                )
                result = cursor.fetchone()
                if result:
                    return result[0]
        return None

    def get_url_blacklist_source(self, url: str) -> Optional[str]:
        """Get the source that blacklisted a URL (exact match)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT source FROM blacklist_url WHERE url = ?",
                (url,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def get_ip_blacklist_source(self, ip: str) -> Optional[str]:
        """Get the source that blacklisted an IP (exact match)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT source FROM blacklist_ip WHERE ip = ?",
                (ip,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def add_domains(self, domains: List[Tuple[str, str, float, str]]):
        """Add multiple domains to the domain blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                domains
            )
            conn.commit()

    def add_urls(self, urls: List[Tuple[str, str, float, str]]):
        """Add multiple URLs to the URL blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                urls
            )
            conn.commit()

    def add_ips(self, ips: List[Tuple[str, str, float, str]]):
        """Add multiple IPs to the IP blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                ips
            )
            conn.commit()

    def log_update(self, source: str, entry_count: int):
        """Log a successful update from a source."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO updates (source, entry_count) VALUES (?, ?)",
                (source, entry_count)
            )
            conn.commit()

    def count_entries(self) -> int:
        """Get total number of blacklist entries (sum of all tables)."""
        with sqlite3.connect(self.db_path) as conn:
            domain_count = conn.execute("SELECT COUNT(*) FROM blacklist_domain").fetchone()[0]
            url_count = conn.execute("SELECT COUNT(*) FROM blacklist_url").fetchone()[0]
            ip_count = conn.execute("SELECT COUNT(*) FROM blacklist_ip").fetchone()[0]
            return domain_count + url_count + ip_count

    def get_source_counts(self) -> Dict[str, int]:
        """Get the number of blacklist entries for each source (all tables)."""
        counts = {}
        with sqlite3.connect(self.db_path) as conn:
            for table in ["blacklist_domain", "blacklist_url", "blacklist_ip"]:
                cursor = conn.execute(f"SELECT source, COUNT(*) FROM {table} GROUP BY source")
                for row in cursor.fetchall():
                    src = row[0]
                    counts[src] = counts.get(src, 0) + row[1]
        return counts

    def get_source_type_counts(self) -> Dict[str, dict]:
        """Get the number of domain, url, and ip entries for each source."""
        stats = {}
        with sqlite3.connect(self.db_path) as conn:
            # Domains
            cursor = conn.execute("SELECT source, COUNT(*) FROM blacklist_domain GROUP BY source")
            for row in cursor.fetchall():
                src = row[0]
                stats.setdefault(src, {"domain": 0, "url": 0, "ip": 0})
                stats[src]["domain"] = row[1]
            # URLs
            cursor = conn.execute("SELECT source, COUNT(*) FROM blacklist_url GROUP BY source")
            for row in cursor.fetchall():
                src = row[0]
                stats.setdefault(src, {"domain": 0, "url": 0, "ip": 0})
                stats[src]["url"] = row[1]
            # IPs
            cursor = conn.execute("SELECT source, COUNT(*) FROM blacklist_ip GROUP BY source")
            for row in cursor.fetchall():
                src = row[0]
                stats.setdefault(src, {"domain": 0, "url": 0, "ip": 0})
                stats[src]["ip"] = row[1]
        return stats

    def get_last_update(self) -> datetime:
        """Get timestamp of last update."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT MAX(timestamp) FROM updates"
            )
            result = cursor.fetchone()[0]
            return datetime.fromisoformat(result) if result else datetime.min

    def get_active_sources(self) -> List[str]:
        """Get list of active blacklist sources (from all tables)."""
        sources = set()
        with sqlite3.connect(self.db_path) as conn:
            for table in ["blacklist_domain", "blacklist_url", "blacklist_ip"]:
                cursor = conn.execute(f"SELECT DISTINCT source FROM {table}")
                sources.update(row[0] for row in cursor.fetchall())
        return list(sources)

    def sample_entries(self, count: int = 10) -> List[str]:
        """Return a random sample of blacklist entries from all tables for testing."""
        entries = []
        with sqlite3.connect(self.db_path) as conn:
            for table, field in [("blacklist_domain", "domain"), ("blacklist_url", "url"), ("blacklist_ip", "ip")]:
                cursor = conn.execute(f"SELECT {field} FROM {table} ORDER BY RANDOM() LIMIT ?", (count,))
                entries.extend(row[0] for row in cursor.fetchall())
        random.shuffle(entries)
        return entries[:count]

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
