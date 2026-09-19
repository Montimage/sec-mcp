import ipaddress
import os
import random
import sqlite3
import sys
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from . import storage_base
from .utility import validate_input


class Storage(storage_base.StorageProtocol):
    """SQLite-based storage with in-memory caching for high-throughput blacklist checks."""

    def __init__(self, db_path=None):
        # resolve_db_path covers the explicit/env/default chain; the platform
        # default is already absolute, so abspath is a no-op for it.
        db_path = storage_base.resolve_db_path(db_path)
        db_path = os.path.abspath(db_path)
        db_dir_from_path = os.path.dirname(db_path)
        if db_dir_from_path:  # Only attempt to create if dirname is not empty
            try:
                os.makedirs(db_dir_from_path, exist_ok=True)
            except OSError as e:
                raise RuntimeError(f"Cannot create database directory {db_dir_from_path}: {e}")
        self.db_path = db_path
        self._cache: Set[str] = set()  # In-memory cache for faster lookups
        self._cache_lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with the shared schema and performance PRAGMAs."""
        try:
            storage_base.init_db(self.db_path)
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Cannot initialize database at {self.db_path}: {e}. Check directory permissions and disk space.")

    def is_domain_blacklisted(self, domain: str) -> bool:
        """Check if a domain or its parent domains are blacklisted."""
        # Check domain and all parent domains
        domain_parts = domain.lower().split('.')
        for i in range(len(domain_parts) - 1):
            sub = '.'.join(domain_parts[i:])
            # Check cache first
            with self._cache_lock:
                if sub in self._cache:
                    return True
            # If not in cache, check DB
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM blacklist_domain WHERE domain = ?",
                    (sub,)
                )
                if cursor.fetchone():
                    with self._cache_lock:
                        self._cache.add(sub) # Add to cache if found in DB
                    return True
        return False

    def is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL is blacklisted (exact match on the canonical form)."""
        # The table stores normalized URLs, so the lookup must normalize too —
        # same function the v2 backend applies, giving identical verdicts.
        url = storage_base.normalize_url(url)
        # Check cache first
        with self._cache_lock:
            if url in self._cache:
                return True
        # If not in cache, check DB
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM blacklist_url WHERE url = ?",
                (url,)
            )
            if cursor.fetchone():
                with self._cache_lock:
                    self._cache.add(url) # Add to cache if found in DB
                return True
        return False

    def is_ip_blacklisted(self, ip: str) -> bool:
        """Check if an IP is blacklisted (either exact match or contained in any network mask)."""
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return False
        # Check cache first for exact IP
        with self._cache_lock:
            if ip in self._cache:
                return True
        # If not in cache, check DB for exact IP
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM blacklist_ip WHERE ip = ?",
                (ip,)
            )
            if cursor.fetchone():
                with self._cache_lock:
                    self._cache.add(ip) # Add exact IP to cache if found
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
                pass # Invalid IP format for 'ip', should not happen if input is validated
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
        """Add a URL to the URL blacklist (stored in canonical form)."""
        url = storage_base.normalize_url(url)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                (url, date, score, source)
            )
            conn.commit()

    def add_ip(self, ip: str, date: str, score: float, source: str):
        """Add an IP to the IP blacklist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                    (ip, date, score, source)
                )
                conn.commit()
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Cannot write to database at {self.db_path}: {e}. Check directory permissions and that the database was initialized properly.")

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
        """Get the source that blacklisted a URL (exact match on the canonical form)."""
        url = storage_base.normalize_url(url)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT source FROM blacklist_url WHERE url = ?",
                (url,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def get_ip_blacklist_source(self, ip: str) -> Optional[str]:
        """Get the source that blacklisted an IP (exact match or containing CIDR range)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT source FROM blacklist_ip WHERE ip = ?",
                (ip,)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            # An IP blacklisted only through a CIDR range still attributes
            # that range's source (same scan is_ip_blacklisted performs).
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                return None
            cursor = conn.execute(
                "SELECT ip, source FROM blacklist_ip WHERE INSTR(ip, '/') > 0"
            )
            for net_str, source in cursor.fetchall():
                try:
                    if addr in ipaddress.ip_network(net_str, strict=False):
                        return source
                except ValueError:
                    # Invalid network string in DB — skip it
                    continue
            return None

    def add_domains(self, domains: List[Tuple[str, str, float, str]]):
        """Add multiple domains to the domain blacklist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                domains
            )
            conn.commit()

    def add_urls(self, urls: List[Tuple[str, str, float, str]]):
        """Add multiple URLs to the URL blacklist (stored in canonical form)."""
        urls = [
            (storage_base.normalize_url(url), date, score, source)
            for url, date, score, source in urls
        ]
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

    def add_entries(self, entries: List[Tuple[Optional[str], Optional[str], str, float, str]]):
        """
        Atomically add feed entries from the blacklist updater.

        Args:
            entries: List of (url, ip, date, score, source) tuples; each entry
                contributes a domain-or-url row plus an optional ip row.

        All inserts happen in a single transaction: on any failure the whole
        batch is rolled back so the live tables are never partially updated.
        """
        domains_to_add = []
        urls_to_add = []
        ips_to_add = []

        for url_val, ip_val, date_val, score_val, source in entries:
            if url_val and url_val.startswith(('http://', 'https://')):
                try:
                    parsed_url = urlparse(url_val)
                    domain = parsed_url.netloc
                    if domain:
                        is_domain_entry = not parsed_url.path or parsed_url.path == '/'
                        if is_domain_entry:
                            if validate_input(domain):
                                domains_to_add.append((domain, date_val, score_val, source))
                        else:
                            urls_to_add.append(
                                (storage_base.normalize_url(url_val), date_val, score_val, source)
                            )
                except Exception:
                    continue
            if ip_val:
                ips_to_add.append((ip_val, date_val, score_val, source))

        with sqlite3.connect(self.db_path) as conn:
            with conn:
                if domains_to_add:
                    conn.executemany(
                        "INSERT OR IGNORE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                        domains_to_add
                    )
                if urls_to_add:
                    conn.executemany(
                        "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                        urls_to_add
                    )
                if ips_to_add:
                    conn.executemany(
                        "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                        ips_to_add
                    )

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

    def flush_cache(self) -> bool:
        """Clear the in-memory URL/IP cache."""
        with self._cache_lock:
            self._cache.clear()
        return True

    def remove_entry(self, value: str) -> bool:
        """Remove a blacklist entry by domain, URL, or IP."""
        # blacklist_url stores the canonical form — the URL delete must use
        # the same normalized value the writes and lookups apply.
        url_normalized = storage_base.normalize_url(value)
        with sqlite3.connect(self.db_path) as conn:
            with conn:
                removed = (
                    conn.execute(
                        "DELETE FROM blacklist_domain WHERE domain = ?",
                        (value,)
                    ).rowcount
                    + conn.execute(
                        "DELETE FROM blacklist_url WHERE url = ?",
                        (url_normalized,)
                    ).rowcount
                    + conn.execute(
                        "DELETE FROM blacklist_ip WHERE ip = ?",
                        (value,)
                    ).rowcount
                )
        # Clear the whole cache: an entry can be cached under a different key
        # than `value` (e.g. a member IP cached after matching a CIDR, or a
        # parent domain cached for a subdomain lookup), so discarding `value`
        # alone would leave stale hits after removal.
        with self._cache_lock:
            self._cache.clear()
        return removed > 0


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
    use_v2 = os.environ.get('MCP_USE_V2_STORAGE', 'false').lower() == 'true'

    if use_v2:
        # v2 explicitly selected: propagate initialization failures instead of
        # silently masking them behind a legacy-storage fallback.
        from .storage_v2 import HybridStorage
        print("Using optimized HybridStorage (v2) - 1000x faster lookups", file=sys.stderr)
        return HybridStorage(db_path)
    else:
        print("Using legacy Storage (v1) - set MCP_USE_V2_STORAGE=true for 1000x faster lookups", file=sys.stderr)
        return Storage(db_path)
