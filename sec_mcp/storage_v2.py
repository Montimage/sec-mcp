"""
High-performance hybrid storage for sec-mcp v0.4.0.

This module provides an in-memory storage implementation with SQLite persistence,
optimized for fast blacklist lookups with minimal disk I/O during queries.

Performance targets (v0.4.0):
- Domain checks: < 0.006ms (1600x faster than DB-only, 40% faster than v0.3.0)
- URL checks: < 0.0007ms (7000x faster, 30% faster than v0.3.0)
- IP+CIDR checks: < 0.007ms (28,000x faster, 30% faster than v0.3.0)
- Memory usage: 40-50MB for 450K entries (30-40% reduction from v0.3.0)

Optimizations:
- One in-memory index per entry type for O(1) lookups
- Source-aware routing to skip irrelevant sources
- URL normalization to reduce duplicates
- Integer-based IP storage for memory efficiency

Layout: ``HybridStorage`` keeps lifecycle and lookup orchestration; the
in-memory structures live in ``sec_mcp.storage_v2_index.EntryIndex``,
SQLite access in ``sec_mcp.storage_v2_db.SQLiteStore``, dual writes in
``sec_mcp.storage_v2_writes.DualWriteMixin``, statistics/reporting in
``sec_mcp.storage_v2_stats.StorageStatsMixin``, and the lookup counters in
``StorageMetrics`` below.
"""

import contextlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

try:
    from .storage_base import StorageProtocol, normalize_url, resolve_db_path
    from .storage_v2_db import SQLiteStore
    from .storage_v2_index import EntryIndex, EntryMetadata, int_to_ip, ip_to_int
    from .storage_v2_stats import StorageStatsMixin
    from .storage_v2_writes import DualWriteMixin
except ImportError:
    # Direct file load (e.g. benchmark.py's spec_from_file_location) has no
    # package context for a relative import.
    from sec_mcp.storage_base import StorageProtocol, normalize_url, resolve_db_path
    from sec_mcp.storage_v2_db import SQLiteStore
    from sec_mcp.storage_v2_index import EntryIndex, EntryMetadata, int_to_ip, ip_to_int
    from sec_mcp.storage_v2_stats import StorageStatsMixin
    from sec_mcp.storage_v2_writes import DualWriteMixin

__all__ = [
    "EntryMetadata",
    "HybridStorage",
    "StorageMetrics",
    "int_to_ip",
    "ip_to_int",
]


@dataclass
class StorageMetrics:
    """Performance metrics for storage operations."""
    total_lookups: int = 0
    domain_lookups: int = 0
    url_lookups: int = 0
    ip_lookups: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_lookup_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    last_reload: Optional[datetime] = None

    # v0.4.0 optimization metrics
    urls_normalized: int = 0
    ips_as_integers: int = 0

    def record(self, lookup_type: str, elapsed_ms: float, found: bool):
        """Update the counters for one completed lookup."""
        self.total_lookups += 1

        if lookup_type == 'domain':
            self.domain_lookups += 1
        elif lookup_type == 'url':
            self.url_lookups += 1
        elif lookup_type == 'ip':
            self.ip_lookups += 1

        if found:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        # Update running average
        if self.total_lookups == 1:
            self.avg_lookup_time_ms = elapsed_ms
        else:
            self.avg_lookup_time_ms = (
                (self.avg_lookup_time_ms * (self.total_lookups - 1) + elapsed_ms)
                / self.total_lookups
            )

    def snapshot(self, entry_count: int, use_pytricia: bool) -> dict:
        """The ``get_metrics`` payload for the current counters."""
        try:
            import psutil
            process = psutil.Process()
            self.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        except (ImportError, OSError):
            # Best-effort metric: psutil missing or the process query failing
            # (its errors subclass OSError) just reports 0.
            self.memory_usage_mb = 0.0

        total_lookups = self.total_lookups

        return {
            "total_lookups": total_lookups,
            "domain_lookups": self.domain_lookups,
            "url_lookups": self.url_lookups,
            "ip_lookups": self.ip_lookups,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.cache_hits / total_lookups if total_lookups > 0 else 0,
            "avg_lookup_time_ms": f"{self.avg_lookup_time_ms:.4f}",
            "memory_usage_mb": f"{self.memory_usage_mb:.1f}",
            "last_reload": self.last_reload.isoformat() if self.last_reload else None,
            "entry_count": entry_count,
            "using_pytricia": use_pytricia,
            # v0.4.0 optimization metrics
            "urls_normalized": self.urls_normalized,
            "ips_as_integers": self.ips_as_integers,
            "optimization_version": "0.4.0"
        }


def _prepare_db_path(db_path: Optional[str]) -> str:
    """Resolve the database path and ensure its parent directory exists.

    Resolution order is explicit arg -> ``MCP_DB_PATH`` -> platform default.
    Unlike Storage (v1) this deliberately does not abspath the result:
    ":memory:" must stay a real in-memory DSN so construction fails closed
    instead of silently creating a file literally named ":memory:".
    """
    db_path = resolve_db_path(db_path)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        try:
            os.makedirs(db_dir, exist_ok=True)
        except OSError as e:
            raise RuntimeError(
                f"Cannot initialize database at {db_path}: {e}. Check directory permissions and disk space."
            ) from e
    return db_path


class HybridStorage(DualWriteMixin, StorageStatsMixin, StorageProtocol):
    """
    High-performance hybrid storage with in-memory lookups and SQLite persistence.

    This storage implementation keeps all blacklist data in memory for O(1) lookups
    while maintaining SQLite persistence for data durability and historical queries.

    Key features (v0.4.0):
    - In-memory sets for domain/URL/IP lookups (O(1) average case)
    - PyTricia radix trees for fast CIDR matching (O(log n))
    - URL normalization to reduce duplicates and memory usage
    - Integer-based IPv4 storage (4 bytes vs 13 bytes)
    - Thread-safe operations with RLock
    - Dual write to memory and database
    - Performance metrics tracking

    Memory footprint: ~40-50MB for 450K entries (30% reduction from v0.3.0)
    Startup time: 5-10 seconds (one-time data loading)
    """

    # Compat seam: the in-memory structures tests reached on the storage
    # object now live on the composed EntryIndex. __getattr__ forwards those
    # names so ``storage._domains`` and friends keep resolving.
    _INDEX_ATTRS = frozenset({
        "_domains", "_urls", "_ips_int", "_ips_str",
        "_domain_meta", "_url_meta", "_ip_meta", "_ip_int_meta",
    })
    _CIDR_ATTRS = frozenset({
        "_cidr_metadata", "_cidr_ranges",
        "_ipv4_cidr_tree", "_ipv6_cidr_tree", "_use_pytricia",
    })

    def __getattr__(self, name):
        # Runs only when normal attribute lookup fails, so every real member
        # resolves first; unknown names still raise AttributeError.
        if name in self._INDEX_ATTRS:
            return getattr(self._index, name)
        if name in self._CIDR_ATTRS:
            return getattr(self._index._cidr, name)
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    def __init__(self, db_path: str = None):
        """
        Initialize hybrid storage.

        Args:
            db_path: Path to SQLite database. If None, uses platform-specific default.
        """
        # Set up logging
        self.logger = logging.getLogger("sec_mcp.storage_v2")

        self.db_path = _prepare_db_path(db_path)

        # Persistence layer — every SQLite call this backend makes goes
        # through this store; nothing below touches the database directly.
        self._db = SQLiteStore(self.db_path)

        # In-memory index — every structure a (re)load replaces lives here,
        # so swapping this one object swaps the whole snapshot atomically.
        self._index = EntryIndex()

        # Thread safety
        self._lock = threading.RLock()
        self._loading = threading.Event()

        # Performance metrics
        self.metrics = StorageMetrics()

        # Initialize database and load data; fail closed on any error so a
        # broken database can never masquerade as an empty blacklist.
        try:
            self._init_db()
            self._load_all_data()
            self._loading.set()
        except Exception as e:  # noqa: BLE001 — fail-closed: any init failure releases waiters and surfaces as RuntimeError
            self._loading.set()
            raise RuntimeError(
                f"Cannot initialize database at {self.db_path}: {e}. Check directory permissions and disk space."
            ) from e

    def _init_db(self):
        """Initialize the database with the shared schema and PRAGMAs."""
        self._db.init_schema()
        self.logger.info(f"Database initialized at {self.db_path}")

    @contextlib.contextmanager
    def shared_connection(self):
        """Uniform connection-scope API — a no-op for the in-memory backend.

        The v1 backend routes every call inside the block through one
        ambient SQLite connection; HybridStorage resolves lookups from
        memory, so the block only scopes the calls — nothing is opened.
        """
        yield self

    def _scratch(self):
        """Return a scratch HybridStorage with an empty in-memory index.

        Reload builds the replacement snapshot on this detached receiver —
        reusing the ``_load_*_from_db`` methods unchanged — while the live
        index stays intact for concurrent readers. Only the swap in
        ``_load_all_data`` mutates what lookups see. It gets its own
        ``SQLiteStore``, so no connection state is shared with the live
        instance.
        """
        builder = object.__new__(HybridStorage)
        builder.db_path = self.db_path
        builder._db = SQLiteStore(self.db_path)
        builder.logger = self.logger
        builder.metrics = self.metrics
        builder._lock = self._lock
        builder._loading = self._loading
        builder._index = self._index.empty_like()
        return builder

    def _load_all_data(self):
        """Load all blacklist data from database into memory.

        The load runs on a scratch instance under the lock — writers keep
        serializing against reload exactly as before — and the populated
        index is then swapped in. Readers never take the lock, so a lookup
        racing the reload sees either the complete previous snapshot or the
        complete new one: a present entry can never appear absent
        mid-reload.
        """
        start_time = time.perf_counter()
        self.logger.info("Loading blacklist data into memory (v0.4.0 optimized)...")

        with self._lock:
            builder = self._scratch()
            builder._load_domains_from_db()
            builder._load_urls_from_db()
            builder._load_ips_from_db()
            self._index = builder._index

        elapsed = time.perf_counter() - start_time
        total_entries = self._index.count()

        self.logger.info(
            f"Loaded {total_entries} entries in {elapsed:.2f}s "
            f"({len(self._index._domains)} domains, "
            f"{len(self._index._urls)} URLs, "
            f"{len(self._index._ips_int) + len(self._index._ips_str)} IPs "
            f"[{len(self._index._ips_int)} as int], "
            f"{self._index._cidr.count()} CIDRs)"
        )

        self.metrics.last_reload = datetime.now()

    def _load_domains_from_db(self):
        """Re-merge domain rows into the live index (batch-write recovery)."""
        self._index.load_domains(self._db.iter_domain_rows())

    def _load_urls_from_db(self):
        """Re-merge URL rows into the live index (batch-write recovery)."""
        self.metrics.urls_normalized = self._index.load_urls(self._db.iter_url_rows())

    def _load_ips_from_db(self):
        """Re-merge IP rows into the live index (batch-write recovery)."""
        self.metrics.ips_as_integers = self._index.load_ips(self._db.iter_ip_rows())

    # ========== Fast Lookup Methods (v0.4.0 Optimized) ==========

    def is_domain_blacklisted(self, domain: str) -> bool:
        """
        Check if a domain or any parent domain is blacklisted.

        Performance: O(depth) where depth is number of domain levels (typically 2-5).
        All lookups are in-memory O(1) hash lookups.

        Args:
            domain: Domain name to check (e.g., "example.com")

        Returns:
            True if domain or any parent is blacklisted, False otherwise

        Examples:
            >>> storage.add_domain("evil.com", "2025-01-01", 9.0, "PhishTank")
            >>> storage.is_domain_blacklisted("evil.com")
            True
            >>> storage.is_domain_blacklisted("sub.evil.com")
            True
        """
        start = time.perf_counter()

        found = self._index.has_domain(domain.lower())

        self._update_metrics('domain', start, found)
        return found

    def is_url_blacklisted(self, url: str) -> bool:
        """
        Check if a URL is blacklisted (exact match with normalization).

        v0.4.0 optimization: normalizes URL before lookup to catch variations.

        Performance: O(1) hash lookup in memory.

        Args:
            url: URL to check (e.g., "http://example.com/path")

        Returns:
            True if URL is blacklisted, False otherwise
        """
        start = time.perf_counter()

        # Normalize URL to catch variations (shared with the v1 backend)
        found = self._index.has_url(normalize_url(url))

        self._update_metrics('url', start, found)
        return found

    def is_ip_blacklisted(self, ip: str) -> bool:
        """
        Check if an IP is blacklisted (exact match or contained in CIDR range).

        v0.4.0 optimizations:
        - Integer-based IPv4 lookups (4x smaller, faster comparison)

        Performance:
        - Exact match: O(1)
        - CIDR with PyTricia: O(log n)

        Args:
            ip: IP address to check (e.g., "192.168.1.1" or "2001:db8::1")

        Returns:
            True if IP is blacklisted, False otherwise
        """
        start = time.perf_counter()

        found = self._index.has_ip(ip)

        self._update_metrics('ip', start, found)
        return found

    def _update_metrics(self, lookup_type: str, start_time: float, found: bool):
        """Update performance metrics."""
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self.metrics.record(lookup_type, elapsed_ms, found)

    # ========== Metadata Retrieval Methods ==========

    def get_domain_blacklist_source(self, domain: str) -> Optional[str]:
        """
        Get the source that blacklisted a domain (including parent domains).

        Args:
            domain: Domain to check

        Returns:
            Source name if blacklisted, None otherwise
        """
        return self._index.domain_source(domain.lower())

    def get_url_blacklist_source(self, url: str) -> Optional[str]:
        """
        Get the source that blacklisted a URL (with normalization).

        Args:
            url: URL to check

        Returns:
            Source name if blacklisted, None otherwise
        """
        return self._index.url_source(normalize_url(url))

    def get_ip_blacklist_source(self, ip: str) -> Optional[str]:
        """
        Get the source that blacklisted an IP (exact match or CIDR).

        Args:
            ip: IP address to check

        Returns:
            Source name if blacklisted, None otherwise
        """
        return self._index.ip_source(ip)

    # ========== Utility Methods ==========

    def flush_cache(self) -> bool:
        """Reload all data from database (equivalent to cache flush)."""
        self.logger.info("Flushing cache (reloading from database)...")
        try:
            self._load_all_data()
            return True
        except Exception as e:  # noqa: BLE001 — the flush contract reports any reload failure as False
            self.logger.error(f"Failed to flush cache: {e}")
            return False

    def reload(self):
        """Reload all data from database."""
        self._load_all_data()

    def get_metrics(self) -> dict:
        """Get current storage performance metrics (v0.4.0 enhanced)."""
        return self.metrics.snapshot(self.count_entries(), self._index._cidr._use_pytricia)
