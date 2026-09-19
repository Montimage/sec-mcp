"""Query and batch-operation half of the v1 ``Storage`` backend.

Every method here works through ``self._connection()`` — the ambient/
per-call SQLite connection the main class provides — plus the positive-hit
cache and CIDR-range invalidations that entry removal and IP batch writes
trigger. Mixed into ``sec_mcp.storage.Storage`` so each half of the backend
stays small enough to read.
"""

import ipaddress
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from . import storage_base
from .utility import validate_input


def _classify_feed_entries(entries):
    """Bucket ``(url, ip, date, score, source)`` feed rows for the batch insert.

    A URL whose path is empty (or a bare ``/``) is a domain-only entry and is
    validated before bucketing; anything with a real path is normalized into
    the URL bucket. Entries with no usable host are dropped entirely.
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

    return domains_to_add, urls_to_add, ips_to_add


class StorageQueryMixin:
    """Source attribution, batch writes, statistics and history for Storage.

    Resolves ``self._connection()``, ``self._invalidate_cidr_ranges()``,
    ``self._cache``/``self._cache_lock`` and ``self.db_path`` on the
    ``Storage`` instance it is mixed into.
    """

    def get_domain_blacklist_source(self, domain: str) -> Optional[str]:
        """Get the source that blacklisted a domain (including parent domains)."""
        domain_parts = domain.lower().split('.')
        with self._connection() as conn:
            for i in range(len(domain_parts) - 1):
                sub = '.'.join(domain_parts[i:])
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
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT source FROM blacklist_url WHERE url = ?",
                (url,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def get_ip_blacklist_source(self, ip: str) -> Optional[str]:
        """Get the source that blacklisted an IP (exact match or containing CIDR range)."""
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT source FROM blacklist_ip WHERE ip = ?",
                (ip,)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            # An IP blacklisted only through a CIDR range still attributes
            # that range's source — matched in memory against the cached
            # ranges, not by re-scanning the table.
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                return None
            for network, source in self._cidr_entries():
                if addr in network:
                    return source
        return None

    def add_domains(self, domains: List[Tuple[str, str, float, str]]):
        """Add multiple domains to the domain blacklist."""
        with self._connection() as conn:
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
        with self._connection() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                urls
            )
            conn.commit()

    def add_ips(self, ips: List[Tuple[str, str, float, str]]):
        """Add multiple IPs to the IP blacklist."""
        with self._connection() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                ips
            )
            conn.commit()
        self._invalidate_cidr_ranges()

    def add_entries(self, entries: List[Tuple[Optional[str], Optional[str], str, float, str]]):
        """
        Atomically add feed entries from the blacklist updater.

        Args:
            entries: List of (url, ip, date, score, source) tuples; each entry
                contributes a domain-or-url row plus an optional ip row.

        All inserts happen in a single transaction: on any failure the whole
        batch is rolled back so the live tables are never partially updated.
        """
        domains_to_add, urls_to_add, ips_to_add = _classify_feed_entries(entries)

        with self._connection() as conn:
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
        if ips_to_add:
            self._invalidate_cidr_ranges()

    def log_update(self, source: str, entry_count: int):
        """Log a successful update from a source."""
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO updates (source, entry_count) VALUES (?, ?)",
                (source, entry_count)
            )
            conn.commit()

    def count_entries(self) -> int:
        """Get total number of blacklist entries (sum of all tables)."""
        with self._connection() as conn:
            domain_count = conn.execute("SELECT COUNT(*) FROM blacklist_domain").fetchone()[0]
            url_count = conn.execute("SELECT COUNT(*) FROM blacklist_url").fetchone()[0]
            ip_count = conn.execute("SELECT COUNT(*) FROM blacklist_ip").fetchone()[0]
            return domain_count + url_count + ip_count

    def get_source_counts(self) -> Dict[str, int]:
        """Get the number of blacklist entries for each source (all tables)."""
        counts = {}
        with self._connection() as conn:
            for table in ["blacklist_domain", "blacklist_url", "blacklist_ip"]:
                cursor = conn.execute(f"SELECT source, COUNT(*) FROM {table} GROUP BY source")
                for row in cursor.fetchall():
                    src = row[0]
                    counts[src] = counts.get(src, 0) + row[1]
        return counts

    def get_source_type_counts(self) -> Dict[str, dict]:
        """Get the number of domain, url, and ip entries for each source."""
        stats = {}
        with self._connection() as conn:
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
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT MAX(timestamp) FROM updates"
            )
            result = cursor.fetchone()[0]
            return datetime.fromisoformat(result) if result else datetime.min

    def get_active_sources(self) -> List[str]:
        """Get list of active blacklist sources (from all tables)."""
        sources = set()
        with self._connection() as conn:
            for table in ["blacklist_domain", "blacklist_url", "blacklist_ip"]:
                cursor = conn.execute(f"SELECT DISTINCT source FROM {table}")
                sources.update(row[0] for row in cursor.fetchall())
        return list(sources)

    def sample_entries(self, count: int = 10) -> List[str]:
        """Return a random sample of blacklist entries from all tables for testing."""
        entries = []
        with self._connection() as conn:
            for table, field in [("blacklist_domain", "domain"), ("blacklist_url", "url"), ("blacklist_ip", "ip")]:
                cursor = conn.execute(f"SELECT {field} FROM {table} ORDER BY RANDOM() LIMIT ?", (count,))
                entries.extend(row[0] for row in cursor.fetchall())
        random.shuffle(entries)
        return entries[:count]

    def get_last_update_per_source(self) -> Dict[str, str]:
        """Get last update timestamp for each source."""
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT source, MAX(timestamp) FROM updates GROUP BY source"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_update_history(self, source: str = None, start: str = None, end: str = None) -> list:
        """Return update history records, optionally filtered by source and time range."""
        with self._connection() as conn:
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

    def remove_entry(self, value: str) -> bool:
        """Remove a blacklist entry by domain, URL, or IP."""
        # blacklist_url stores the canonical form — the URL delete must use
        # the same normalized value the writes and lookups apply.
        url_normalized = storage_base.normalize_url(value)
        with self._connection() as conn:
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
        # Clear the whole positive-hit cache: an entry can be cached under a
        # different key than `value` (e.g. a member IP cached after matching
        # a CIDR, or a parent domain cached for a subdomain lookup), so
        # discarding `value` alone would leave stale hits after removal.
        # Cached CIDR ranges are invalidated too: a removed range must stop
        # matching its member IPs immediately.
        with self._cache_lock:
            self._cache.clear()
        self._invalidate_cidr_ranges()
        return removed > 0
