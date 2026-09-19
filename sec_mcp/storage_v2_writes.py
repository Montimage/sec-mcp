"""Dual-write methods for HybridStorage (v0.4.0).

Every write a HybridStorage accepts updates the in-memory ``EntryIndex``
first and persists through ``SQLiteStore`` second, rolling the memory change
back (or reloading the pool) when the database write fails. These methods
are the write half of ``sec_mcp.storage_v2.HybridStorage``, mixed in so each
half stays small enough to read.
"""

import ipaddress
import sqlite3
from typing import List, Optional, Tuple
from urllib.parse import urlparse

try:
    from .storage_base import normalize_url
    from .storage_v2_index import EntryMetadata, ip_to_int
except ImportError:
    # Direct file load (e.g. benchmark.py's spec_from_file_location) has no
    # package context for a relative import.
    from sec_mcp.storage_base import normalize_url
    from sec_mcp.storage_v2_index import EntryMetadata, ip_to_int


def _bucket_feed_entries(entries):
    """Split ``(url, ip, date, score, source)`` feed rows by entry type.

    A URL whose path is empty (or a bare ``/``) is a domain-only entry;
    anything with a real path stays a URL entry.
    """
    domains_to_add = []
    urls_to_add = []
    ips_to_add = []

    for url_val, ip_val, date_val, score_val, source in entries:
        if ip_val:
            ips_to_add.append((ip_val, date_val, score_val, source))

        if url_val and url_val.startswith(('http://', 'https://')):
            # Determine if it's a domain-only URL or a full URL
            try:
                parsed = urlparse(url_val)
            except (ValueError, TypeError):
                # urlparse rejects malformed URLs; the row is skipped.
                continue
            domain = parsed.netloc
            is_domain_entry = not parsed.path or parsed.path == '/'
            if is_domain_entry and domain:
                domains_to_add.append((domain, date_val, score_val, source))
            else:
                urls_to_add.append((url_val, date_val, score_val, source))

    return domains_to_add, urls_to_add, ips_to_add


class DualWriteMixin:
    """The add_*/remove_entry half of HybridStorage — memory + database.

    Mixed into ``HybridStorage``; every method resolves ``self._lock``,
    ``self._index``, ``self._db``, ``self.logger`` and the
    ``self._load_*_from_db`` recovery reloads on the storage instance.
    """

    def add_domain(self, domain: str, date: str, score: float, source: str):
        """
        Add a domain to both memory and database.

        Args:
            domain: Domain name
            date: Date string (ISO format recommended)
            score: Threat score (0-10)
            source: Source name
        """
        with self._lock:
            domain_lower = domain.lower()

            # Update memory first
            self._index.add_domain(domain_lower, EntryMetadata(source, date, score))

            # Persist to database
            try:
                self._db.upsert_domain(domain, date, score, source)
            except (OSError, sqlite3.Error) as e:
                # Rollback memory changes on DB failure
                self._index.discard_domain(domain_lower)
                self.logger.error(f"Failed to add domain to database: {e}")
                raise

    def add_url(self, url: str, date: str, score: float, source: str):
        """Add a URL to both memory and database with normalization."""
        with self._lock:
            # Normalize URL — the canonical form is what memory, the database
            # and the v1 backend all agree on.
            url_normalized = normalize_url(url)

            # Update memory first
            self._index.add_url(url_normalized, EntryMetadata(source, date, score))

            # Persist the canonical form so v1's exact-match lookups agree
            try:
                self._db.upsert_url(url_normalized, date, score, source)
            except (OSError, sqlite3.Error) as e:
                # Rollback
                self._index.discard_url(url_normalized)
                self.logger.error(f"Failed to add URL to database: {e}")
                raise

    def add_ip(self, ip: str, date: str, score: float, source: str):
        """Add an IP or CIDR range to both memory and database.

        Raises:
            ValueError: if ``ip`` is not a valid IP address or CIDR range
                (e.g. an out-of-range octet like ``1.2.3.999``).
        """
        with self._lock:
            # Reject malformed input before any state changes: an out-of-range
            # IPv4 octet otherwise silently aliases a different address in
            # integer storage, and pytricia raises SystemError on bad keys.
            if '/' in ip:
                ipaddress.ip_network(ip, strict=False)
            else:
                ipaddress.ip_address(ip)

            # Determine if CIDR or single IP
            is_cidr = '/' in ip
            ip_int = None if is_cidr else ip_to_int(ip)

            # Update memory first
            self._index.add_ip(ip, source, EntryMetadata(source, date, score))

            # Persist to database
            try:
                self._db.upsert_ip(ip, date, score, source)
            except (OSError, sqlite3.Error) as e:
                # Rollback
                self._index.discard_ip(ip, is_cidr, ip_int)
                self.logger.error(f"Failed to add IP to database: {e}")
                raise

    def add_domains(self, domains: List[Tuple[str, str, float, str]]):
        """Add multiple domains efficiently (batch operation)."""
        with self._lock:
            # Update memory
            self._index.add_domains(domains)

            # Persist to database in transaction
            try:
                self._db.upsert_domains(domains)
            except (OSError, sqlite3.Error) as e:
                self.logger.error(f"Failed to add domains batch: {e}")
                # Roll back the memory inserts — the re-merge is additive and
                # alone would leave phantom entries the DB never stored.
                for domain, *_ in domains:
                    self._index.discard_domain(domain.lower())
                # Re-merge DB truth so rows that pre-existed are restored.
                self._load_domains_from_db()
                raise

    def add_urls(self, urls: List[Tuple[str, str, float, str]]):
        """Add multiple URLs efficiently (batch operation with normalization)."""
        with self._lock:
            # Update memory — and collect the canonical forms to persist so
            # v1's exact-match lookups agree.
            normalized_rows = self._index.add_urls(urls)

            # Persist the canonical forms so v1's exact-match lookups agree
            try:
                self._db.upsert_urls(normalized_rows)
            except (OSError, sqlite3.Error) as e:
                self.logger.error(f"Failed to add URLs batch: {e}")
                # Roll back the memory inserts — the re-merge is additive and
                # alone would leave phantom entries the DB never stored.
                for url_normalized, *_ in normalized_rows:
                    self._index.discard_url(url_normalized)
                # Re-merge DB truth so rows that pre-existed are restored.
                self._load_urls_from_db()
                raise

    def add_ips(self, ips: List[Tuple[str, str, float, str]]):
        """Add multiple IPs efficiently (batch operation with integer storage)."""
        with self._lock:
            # Update memory — and collect only the entries that validate, so
            # skipped input can never drift between memory and the database.
            persist = self._index.add_ips(ips)

            # Persist to database
            try:
                self._db.upsert_ips(persist)
            except (OSError, sqlite3.Error) as e:
                self.logger.error(f"Failed to add IPs batch: {e}")
                # Roll back the memory inserts — the re-merge is additive and
                # alone would leave phantom entries the DB never stored.
                for ip, *_ in persist:
                    is_cidr = '/' in ip
                    ip_int = None if is_cidr else ip_to_int(ip)
                    self._index.discard_ip(ip, is_cidr, ip_int)
                # Re-merge DB truth so rows that pre-existed are restored.
                self._load_ips_from_db()
                raise

    def add_entries(self, entries: List[Tuple[str, Optional[str], str, float, str]]):
        """
        Add entries from blacklist updater (legacy compatibility).

        Args:
            entries: List of (url, ip, date, score, source) tuples
        """
        domains_to_add, urls_to_add, ips_to_add = _bucket_feed_entries(entries)

        if domains_to_add:
            self.add_domains(domains_to_add)
        if urls_to_add:
            self.add_urls(urls_to_add)
        if ips_to_add:
            self.add_ips(ips_to_add)

    def remove_entry(self, value: str) -> bool:
        """Remove an entry from both memory and database."""
        with self._lock:
            value_normalized = normalize_url(value)
            removed = self._index.remove(value, value_normalized)

            if removed:
                # Remove from database — blacklist_url holds the canonical
                # form, so the URL delete must use the normalized value.
                self._db.delete_entry(value, value_normalized)

            return removed
