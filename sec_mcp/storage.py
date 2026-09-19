import contextlib
import ipaddress
import os
import sqlite3
import sys
import threading
from collections import OrderedDict
from typing import List, Optional, Tuple

from . import storage_base
from .storage_queries import StorageQueryMixin
from .utility import load_config


class Storage(StorageQueryMixin, storage_base.StorageProtocol):
    """SQLite-based storage with in-memory caching for high-throughput blacklist checks.

    This half owns connection scoping, the positive-hit cache, the cached
    CIDR ranges, the single-entry lookups/writes and cache lifecycle; the
    source-attribution, batch-write, statistics and history methods live in
    :class:`sec_mcp.storage_queries.StorageQueryMixin`.
    """

    def __init__(self, db_path=None, cache_size: Optional[int] = None):
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

        # Bounded positive-hit cache (OrderedDict used as an LRU set): a
        # lookup that found an entry blacklisted replays from memory, and
        # the oldest hits are evicted once the configured max size is
        # exceeded. ``cache_size`` defaults to config.json's "cache_size".
        if cache_size is None:
            try:
                cache_size = int(load_config().get("cache_size", 10000))
            except (OSError, TypeError, ValueError):
                cache_size = 10000
        self._cache_max_size = max(0, int(cache_size))
        self._cache: "OrderedDict[str, None]" = OrderedDict()
        self._cache_lock = threading.Lock()

        # Thread-local ambient connection installed by shared_connection().
        self._local = threading.local()

        # Parsed CIDR ranges paired with their sources, loaded lazily once
        # and matched in memory so an IP lookup never scans the whole
        # blacklist_ip table. None means "not loaded": a write to the ip
        # table or flush_cache() invalidates back to None for a reload.
        self._cidr_ranges: Optional[List[Tuple[object, str]]] = None
        self._cidr_lock = threading.Lock()

        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with the shared schema and performance PRAGMAs."""
        try:
            storage_base.init_db(self.db_path)
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Cannot initialize database at {self.db_path}: {e}. Check directory permissions and disk space.")

    @contextlib.contextmanager
    def _connection(self):
        """Yield the connection this call runs on.

        Inside another ``_connection()``/``shared_connection()`` block the
        ambient connection is reused; the outermost call on this thread
        opens a fresh one, installs it as ambient for nested calls, and
        closes it on exit — one ``sqlite3.connect`` per outermost call.
        """
        ambient = getattr(self._local, "conn", None)
        if ambient is not None:
            yield ambient
            return
        conn = sqlite3.connect(self.db_path)
        self._local.conn = conn
        try:
            yield conn
        finally:
            self._local.conn = None
            conn.close()

    @contextlib.contextmanager
    def shared_connection(self):
        """Run a sequence of storage calls on a single SQLite connection.

        Calls made on this thread inside the block reuse the ambient
        connection instead of opening one per call, so a ``SecMCP.check()``
        costs exactly one ``sqlite3.connect`` no matter how many storage
        methods it touches. Reentrant: nested blocks share the outer
        connection.
        """
        with self._connection() as conn:
            yield conn

    def _cache_get(self, key: str) -> bool:
        """Cache hit check that also refreshes recency for LRU eviction."""
        with self._cache_lock:
            if key not in self._cache:
                return False
            self._cache.move_to_end(key)
            return True

    def _cache_put(self, key: str) -> None:
        """Insert into the bounded cache, evicting oldest hits past max size."""
        if self._cache_max_size <= 0:
            return
        with self._cache_lock:
            self._cache[key] = None
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_max_size:
                self._cache.popitem(last=False)

    def _cidr_entries(self) -> List[Tuple[object, str]]:
        """Parsed CIDR ranges and their sources, loaded once then cached.

        The one SELECT this pays fetches only CIDR rows; every later IP
        lookup matches in memory — zero full-table CIDR scans per lookup.

        The whole load runs under ``_cidr_lock``: a writer always commits
        *before* calling ``_invalidate_cidr_ranges``, so serializing the
        check + fetch + store against invalidation means a range list read
        before a commit can never be stored after that commit's
        invalidation — the stale store would otherwise leave a new CIDR
        permanently unmatched until the next write.
        """
        with self._cidr_lock:
            if self._cidr_ranges is not None:
                return self._cidr_ranges
            with self._connection() as conn:
                rows = conn.execute(
                    "SELECT ip, source FROM blacklist_ip WHERE INSTR(ip, '/') > 0"
                ).fetchall()
            ranges = []
            for net_str, source in rows:
                try:
                    ranges.append((ipaddress.ip_network(net_str, strict=False), source))
                except ValueError:
                    # Invalid network string in DB — skip it, exactly as the
                    # per-lookup scan used to.
                    continue
            self._cidr_ranges = ranges
            return ranges

    def _invalidate_cidr_ranges(self) -> None:
        """Drop the cached CIDR ranges after a write to blacklist_ip."""
        with self._cidr_lock:
            self._cidr_ranges = None

    def is_domain_blacklisted(self, domain: str) -> bool:
        """Check if a domain or its parent domains are blacklisted."""
        # Check the domain and all parent domains: the whole cache first —
        # a fully-cached chain never opens a connection — then the DB on a
        # single connection (the loop used to open one connect per level).
        domain_parts = domain.lower().split('.')
        subs = ['.'.join(domain_parts[i:]) for i in range(len(domain_parts) - 1)]
        for sub in subs:
            if self._cache_get(sub):
                return True
        with self._connection() as conn:
            for sub in subs:
                cursor = conn.execute(
                    "SELECT 1 FROM blacklist_domain WHERE domain = ?",
                    (sub,)
                )
                if cursor.fetchone():
                    self._cache_put(sub) # Add to cache if found in DB
                    return True
        return False

    def is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL is blacklisted (exact match on the canonical form)."""
        # The table stores normalized URLs, so the lookup must normalize too —
        # same function the v2 backend applies, giving identical verdicts.
        url = storage_base.normalize_url(url)
        # Check cache first
        if self._cache_get(url):
            return True
        # If not in cache, check DB
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM blacklist_url WHERE url = ?",
                (url,)
            )
            if cursor.fetchone():
                self._cache_put(url) # Add to cache if found in DB
                return True
        return False

    def is_ip_blacklisted(self, ip: str) -> bool:
        """Check if an IP is blacklisted (either exact match or contained in any network mask)."""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        # Check cache first for exact IP
        if self._cache_get(ip):
            return True
        # If not in cache, check DB for exact IP
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM blacklist_ip WHERE ip = ?",
                (ip,)
            )
            if cursor.fetchone():
                self._cache_put(ip) # Add exact IP to cache if found
                return True

            # CIDR membership is matched against the cached in-memory ranges
            # (_cidr_entries) instead of re-scanning every CIDR row per lookup;
            # a cold load reuses this same connection. A positive CIDR match
            # means the IP is bad, so it is cached like an exact hit —
            # remove_entry still clears the whole cache.
            for network, _source in self._cidr_entries():
                if addr in network:
                    self._cache_put(ip)
                    return True
        return False

    def add_domain(self, domain: str, date: str, score: float, source: str):
        """Add a domain to the domain blacklist."""
        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                (domain, date, score, source)
            )
            conn.commit()

    def add_url(self, url: str, date: str, score: float, source: str):
        """Add a URL to the URL blacklist (stored in canonical form)."""
        url = storage_base.normalize_url(url)
        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                (url, date, score, source)
            )
            conn.commit()

    def add_ip(self, ip: str, date: str, score: float, source: str):
        """Add an IP to the IP blacklist."""
        try:
            with self._connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                    (ip, date, score, source)
                )
                conn.commit()
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Cannot write to database at {self.db_path}: {e}. Check directory permissions and that the database was initialized properly.")
        # A new CIDR row changes what member IPs match — reload lazily.
        self._invalidate_cidr_ranges()

    def flush_cache(self) -> bool:
        """Clear the in-memory positive-hit cache and cached CIDR ranges."""
        with self._cache_lock:
            self._cache.clear()
        self._invalidate_cidr_ranges()
        return True


def create_storage(db_path=None):
    """
    Factory function to create the appropriate storage instance based on configuration.

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
