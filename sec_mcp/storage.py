import os
import random
import sqlite3
import sys
import threading
from datetime import datetime
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
                    db_dir = os.path.join(
                        os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")),
                        "sec-mcp",
                    )
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
            # Ensure db_path is absolute
            db_path = os.path.abspath(db_path)
            db_dir_from_path = os.path.dirname(db_path)
            if db_dir_from_path:  # Only attempt to create if dirname is not empty
                try:
                    os.makedirs(db_dir_from_path, exist_ok=True)
                except OSError as e:
                    raise RuntimeError(f"Cannot create database directory {db_dir_from_path}: {e}")
        self.db_path = db_path
        self._cache: set[str] = set()  # In-memory cache for faster lookups
        self._cache_lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with required tables and performance PRAGMAs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA cache_size=10000;")
                # Create new blacklist tables for domain, url, and ip
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS blacklist_domain (
                        domain TEXT PRIMARY KEY,
                        date TEXT,
                        score REAL,
                        source TEXT
                    )
                """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_blacklist_domain ON blacklist_domain(domain);
                """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS blacklist_url (
                        url TEXT PRIMARY KEY,
                        date TEXT,
                        score REAL,
                        source TEXT
                    )
                """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_blacklist_url ON blacklist_url(url);
                """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS blacklist_ip (
                        ip TEXT PRIMARY KEY,
                        date TEXT,
                        score REAL,
                        source TEXT
                    )
                """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_blacklist_ip ON blacklist_ip(ip);
                """
                )
                # Create updates table (unchanged)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS updates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        source TEXT NOT NULL,
                        entry_count INTEGER NOT NULL
                    )
                """
                )
                conn.commit()
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"Cannot initialize database at {self.db_path}: {e}. Check directory permissions and disk space."
            )

    def is_domain_blacklisted(self, domain: str) -> bool:
        """Check if a domain or its parent domains are blacklisted."""
        # Check domain and all parent domains
        domain_parts = domain.lower().split(".")
        for i in range(len(domain_parts) - 1):
            sub = ".".join(domain_parts[i:])
            # Check cache first
            with self._cache_lock:
                if sub in self._cache:
                    return True
            # If not in cache, check DB
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT 1 FROM blacklist_domain WHERE domain = ?", (sub,))
                if cursor.fetchone():
                    with self._cache_lock:
                        self._cache.add(sub)  # Add to cache if found in DB
                    return True
        return False

    def is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL is blacklisted (exact match)."""
        # Check cache first
        with self._cache_lock:
            if url in self._cache:
                return True
        # If not in cache, check DB
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM blacklist_url WHERE url = ?", (url,))
            if cursor.fetchone():
                with self._cache_lock:
                    self._cache.add(url)  # Add to cache if found in DB
                return True
        return False

    def is_ip_blacklisted(self, ip: str) -> bool:
        """Check if an IP is blacklisted (either exact match or contained in any network mask)."""
        import ipaddress

        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return False
        # Check cache first for exact IP
        with self._cache_lock:
            if ip in self._cache:
                return True
        # If not in cache, check DB for exact IP
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM blacklist_ip WHERE ip = ?", (ip,))
            if cursor.fetchone():
                with self._cache_lock:
                    self._cache.add(ip)  # Add exact IP to cache if found
                return True

            # Check for network mask (this part is more complex and less cacheable directly without processing all masks)
            # The current implementation checks all network masks, which might be slow.
            # For CIDR matches, we won't cache the specific IP 'ip' under the CIDR key directly here,
            # as the cache is for exact matches. A positive CIDR match means the IP is bad,
            # but caching 'ip' itself might be misleading if 'ip' isn't an exact entry.
            # However, if an IP is found via CIDR, it IS blacklisted.
            cursor = conn.execute(
                "SELECT ip FROM blacklist_ip WHERE INSTR(ip, '/') > 0"  # Select only CIDRs
            )
            try:
                addr = ipaddress.ip_address(ip)
                for row in cursor.fetchall():
                    net_str = row[0]
                    # Ensure net_str is a valid network before creating ip_network object
                    try:
                        network = ipaddress.ip_network(net_str, strict=False)
                        if addr in network:
                            # We found it via CIDR. We can cache the specific IP as blacklisted.
                            with self._cache_lock:
                                self._cache.add(ip)
                            return True
                    except ValueError:
                        # Invalid network string in DB, log or handle as appropriate
                        continue
            except ValueError:
                pass  # Invalid IP format for 'ip', should not happen if input is validated
        return False

    def add_domain(self, domain: str, date: str, score: float, source: str):
        """Add a domain to the domain blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                (domain, date, score, source),
            )
            conn.commit()

    def add_url(self, url: str, date: str, score: float, source: str):
        """Add a URL to the URL blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                (url, date, score, source),
            )
            conn.commit()

    def add_ip(self, ip: str, date: str, score: float, source: str):
        """Add an IP to the IP blacklist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                    (ip, date, score, source),
                )
                conn.commit()
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"Cannot write to database at {self.db_path}: {e}. Check directory permissions and that the database was initialized properly."
            )

    def remove_domain(self, domain: str) -> bool:
        """Remove a domain from the domain blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM blacklist_domain WHERE domain = ?", (domain,))
            conn.commit()
        return cursor.rowcount > 0

    def remove_url(self, url: str) -> bool:
        """Remove a URL from the URL blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM blacklist_url WHERE url = ?", (url,))
            conn.commit()
        return cursor.rowcount > 0

    def remove_ip(self, ip: str) -> bool:
        """Remove an IP from the IP blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM blacklist_ip WHERE ip = ?", (ip,))
            conn.commit()
        return cursor.rowcount > 0

    def get_domain_blacklist_source(self, domain: str) -> str | None:
        """Get the source that blacklisted a domain (including parent domains)."""
        domain_parts = domain.lower().split(".")
        for i in range(len(domain_parts) - 1):
            sub = ".".join(domain_parts[i:])
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT source FROM blacklist_domain WHERE domain = ?", (sub,)
                )
                result = cursor.fetchone()
                if result:
                    return result[0]
        return None

    def get_url_blacklist_source(self, url: str) -> str | None:
        """Get the source that blacklisted a URL (exact match)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT source FROM blacklist_url WHERE url = ?", (url,))
            result = cursor.fetchone()
            return result[0] if result else None

    def get_ip_blacklist_source(self, ip: str) -> str | None:
        """Get the source that blacklisted an IP (exact match)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT source FROM blacklist_ip WHERE ip = ?", (ip,))
            result = cursor.fetchone()
            return result[0] if result else None

    def add_domains(self, domains: list[tuple[str, str, float, str]]):
        """Add multiple domains to the domain blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                domains,
            )
            conn.commit()

    def add_urls(self, urls: list[tuple[str, str, float, str]]):
        """Add multiple URLs to the URL blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                urls,
            )
            conn.commit()

    def add_ips(self, ips: list[tuple[str, str, float, str]]):
        """Add multiple IPs to the IP blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                ips,
            )
            conn.commit()

    def log_update(self, source: str, entry_count: int):
        """Log a successful update from a source."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO updates (source, entry_count) VALUES (?, ?)", (source, entry_count)
            )
            conn.commit()

    def count_entries(self) -> int:
        """Get total number of blacklist entries (sum of all tables)."""
        with sqlite3.connect(self.db_path) as conn:
            domain_count = conn.execute("SELECT COUNT(*) FROM blacklist_domain").fetchone()[0]
            url_count = conn.execute("SELECT COUNT(*) FROM blacklist_url").fetchone()[0]
            ip_count = conn.execute("SELECT COUNT(*) FROM blacklist_ip").fetchone()[0]
            return domain_count + url_count + ip_count

    def get_source_counts(self) -> dict[str, int]:
        """Get the number of blacklist entries for each source (all tables)."""
        counts = {}
        with sqlite3.connect(self.db_path) as conn:
            for table in ["blacklist_domain", "blacklist_url", "blacklist_ip"]:
                cursor = conn.execute(f"SELECT source, COUNT(*) FROM {table} GROUP BY source")
                for row in cursor.fetchall():
                    src = row[0]
                    counts[src] = counts.get(src, 0) + row[1]
        return counts

    def get_source_type_counts(self) -> dict[str, dict]:
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
            cursor = conn.execute("SELECT MAX(timestamp) FROM updates")
            result = cursor.fetchone()[0]
            return datetime.fromisoformat(result) if result else datetime.min

    def get_active_sources(self) -> list[str]:
        """Get list of active blacklist sources (from all tables)."""
        sources = set()
        with sqlite3.connect(self.db_path) as conn:
            for table in ["blacklist_domain", "blacklist_url", "blacklist_ip"]:
                cursor = conn.execute(f"SELECT DISTINCT source FROM {table}")
                sources.update(row[0] for row in cursor.fetchall())
        return list(sources)

    def sample_entries(self, count: int = 10) -> list[str]:
        """Return a random sample of blacklist entries from all tables for testing."""
        entries = []
        with sqlite3.connect(self.db_path) as conn:
            for table, field in [
                ("blacklist_domain", "domain"),
                ("blacklist_url", "url"),
                ("blacklist_ip", "ip"),
            ]:
                cursor = conn.execute(
                    f"SELECT {field} FROM {table} ORDER BY RANDOM() LIMIT ?", (count,)
                )
                entries.extend(row[0] for row in cursor.fetchall())
        random.shuffle(entries)
        return entries[:count]

    def get_last_update_per_source(self) -> dict[str, str]:
        """Get last update timestamp for each source."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT source, MAX(timestamp) FROM updates GROUP BY source")
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
            cursor = conn.execute("DELETE FROM blacklist WHERE url = ? OR ip = ?", (value, value))
            conn.commit()
        with self._cache_lock:
            self._cache.discard(value)
        return cursor.rowcount > 0


def create_storage(db_path=None):
    """
    Factory function to create storage instance based on configuration.

    Uses environment variable MCP_USE_V2_STORAGE to determine which storage
    implementation to use:
    - 'true': Use HybridStorage (v2) with in-memory optimization
    - 'false' or unset: Use legacy Storage (v1) with database-only

    Args:
        db_path: Path to SQLite database

    Returns:
        Storage or HybridStorage instance
    """
    use_v2 = os.environ.get("MCP_USE_V2_STORAGE", "false").lower() == "true"

    if use_v2:
        try:
            import sys

            from .storage_v2 import HybridStorage

            print("Using optimized HybridStorage (v2) - 1000x faster lookups", file=sys.stderr)
            return HybridStorage(db_path)
        except Exception as e:
            import sys

            print(f"Warning: Failed to initialize HybridStorage: {e}", file=sys.stderr)
            print("Falling back to legacy Storage (v1)", file=sys.stderr)
            return Storage(db_path)
    else:
        import sys

        print(
            "Using legacy Storage (v1) - set MCP_USE_V2_STORAGE=true for 1000x faster lookups",
            file=sys.stderr,
        )
        return Storage(db_path)
