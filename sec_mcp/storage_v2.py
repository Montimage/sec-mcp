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
- Tiered lookup (hot/cold sources) for early exit
- Source-aware routing to skip irrelevant sources
- URL normalization to reduce duplicates
- Integer-based IP storage for memory efficiency
"""

import ipaddress
import itertools
import logging
import os
import random
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    from .storage_base import StorageProtocol, init_db, resolve_db_path
except ImportError:
    # Direct file load (e.g. benchmark.py's spec_from_file_location) has no
    # package context for a relative import.
    from sec_mcp.storage_base import StorageProtocol, init_db, resolve_db_path

# ========== Source Classification ==========
# Based on production data analysis (449K entries)

# Hot URL sources (74% of URLs - PhishTank + URLhaus = 153K/207K)
HOT_URL_SOURCES = frozenset(['PhishTank', 'URLhaus'])

# Hot IP sources (90% of IPs - BlocklistDE + CINSSCORE = 126K/141K)
HOT_IP_SOURCES = frozenset(['BlocklistDE', 'CINSSCORE'])

# Hot domain sources (major phishing databases)
HOT_DOMAIN_SOURCES = frozenset(['PhishTank', 'PhishStats'])


@dataclass
class EntryMetadata:
    """Metadata for a blacklist entry."""
    source: str
    date: str
    score: float


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
    hot_source_hits: int = 0
    cold_source_hits: int = 0
    urls_normalized: int = 0
    ips_as_integers: int = 0


def normalize_url(url: str) -> str:
    """
    Normalize URL to reduce duplicates.

    Normalization:
    - Convert to lowercase
    - Remove tracking parameters (utm_*, fbclid, etc.)
    - Strip trailing slashes from path
    - Ensure scheme (default to http if missing)

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string

    Examples:
        >>> normalize_url("HTTP://EVIL.COM/")
        "http://evil.com"
        >>> normalize_url("http://evil.com/?utm_source=spam")
        "http://evil.com"
    """
    try:
        # Parse URL
        parsed = urlparse(url.lower())

        # Filter out tracking parameters
        if parsed.query:
            query_params = parse_qs(parsed.query)
            # Remove common tracking parameters
            tracking_params = {
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'mc_eid', '_ga', 'ref', 'referrer'
            }
            filtered_params = {
                k: v for k, v in query_params.items()
                if k.lower() not in tracking_params
            }
            query_string = urlencode(filtered_params, doseq=True)
        else:
            query_string = ''

        # Rebuild URL
        normalized = urlunparse((
            parsed.scheme or 'http',  # Default scheme
            parsed.netloc,
            parsed.path.rstrip('/') or '/',  # Remove trailing slash
            '',  # params (deprecated)
            query_string,
            ''  # fragment (ignore)
        ))

        return normalized
    except Exception:
        # If normalization fails, return original lowercase
        return url.lower()


def ip_to_int(ip: str) -> Optional[int]:
    """
    Convert IP address string to integer for compact storage.

    IPv4: Stores as 32-bit integer (4 bytes vs ~13 bytes string)
    IPv6: Returns None (stick with string for now, PyTricia handles well)

    Args:
        ip: IP address string

    Returns:
        Integer representation of IPv4, or None for IPv6/invalid

    Examples:
        >>> ip_to_int("192.168.1.1")
        3232235777
        >>> ip_to_int("10.0.0.1")
        167772161
    """
    try:
        if ':' in ip:
            # IPv6 - too large for int, keep as string
            return None

        # IPv4 - convert to 32-bit integer
        parts = ip.split('.')
        if len(parts) != 4:
            return None

        octets = [int(part) for part in parts]
        # Reject out-of-range octets: without this check "1.2.3.999" sums to
        # the same integer as "1.2.6.231", so an invalid address aliases a
        # different, real one.
        if any(octet < 0 or octet > 255 for octet in octets):
            return None

        return (
            (octets[0] << 24) +
            (octets[1] << 16) +
            (octets[2] << 8) +
            octets[3]
        )
    except (ValueError, IndexError):
        return None


def int_to_ip(ip_int: int) -> str:
    """
    Convert integer back to IPv4 string.

    Args:
        ip_int: 32-bit integer

    Returns:
        IPv4 address string
    """
    return '.'.join([
        str((ip_int >> 24) & 0xFF),
        str((ip_int >> 16) & 0xFF),
        str((ip_int >> 8) & 0xFF),
        str(ip_int & 0xFF)
    ])


class HybridStorage(StorageProtocol):
    """
    High-performance hybrid storage with in-memory lookups and SQLite persistence.

    This storage implementation keeps all blacklist data in memory for O(1) lookups
    while maintaining SQLite persistence for data durability and historical queries.

    Key features (v0.4.0):
    - In-memory sets for domain/URL/IP lookups (O(1) average case)
    - PyTricia radix trees for fast CIDR matching (O(log n))
    - Tiered lookup (hot/cold sources) for early exit optimization
    - URL normalization to reduce duplicates and memory usage
    - Integer-based IPv4 storage (4 bytes vs 13 bytes)
    - Thread-safe operations with RLock
    - Dual write to memory and database
    - Performance metrics tracking

    Memory footprint: ~40-50MB for 450K entries (30% reduction from v0.3.0)
    Startup time: 5-10 seconds (one-time data loading)
    """

    # Every in-memory structure a (re)load replaces. _load_all_data builds
    # these on a scratch instance and swaps them in under the lock, so a
    # concurrent reader always observes a complete snapshot — the previous
    # one or the new one — and never a cleared table.
    _SNAPSHOT_ATTRS = (
        "_domains", "_urls",
        "_hot_domains", "_cold_domains",
        "_hot_urls", "_cold_urls",
        "_ips_int", "_ips_str",
        "_hot_ips_int", "_cold_ips_int",
        "_hot_ips_str", "_cold_ips_str",
        "_domain_meta", "_url_meta",
        "_ip_meta", "_ip_int_meta",
        "_cidr_metadata", "_cidr_ranges",
        "_ipv4_cidr_tree", "_ipv6_cidr_tree",
    )

    def __init__(self, db_path: str = None):
        """
        Initialize hybrid storage.

        Args:
            db_path: Path to SQLite database. If None, uses platform-specific default.
        """
        # Set up logging
        self.logger = logging.getLogger("sec_mcp.storage_v2")

        # Resolve database path (explicit arg -> MCP_DB_PATH -> platform default).
        # Unlike Storage (v1) this deliberately does not abspath the result:
        # ":memory:" must stay a real in-memory DSN so construction fails closed
        # instead of silently creating a file literally named ":memory:".
        db_path = resolve_db_path(db_path)

        # Create directory if needed
        db_dir = os.path.dirname(db_path)
        if db_dir:
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError as e:
                raise RuntimeError(
                    f"Cannot initialize database at {db_path}: {e}. Check directory permissions and disk space."
                ) from e

        self.db_path = db_path

        # ========== In-memory data structures ==========

        # Unified storage for domains and URLs (kept for backward compatibility).
        # Single IPs deliberately have no legacy set here: _ips_int/_ips_str
        # already hold every address exactly once, so a third mirror only
        # double-counted entries and duplicated attribution metadata.
        self._domains: Set[str] = set()
        self._urls: Set[str] = set()

        # v0.4.0: Tiered storage for optimized lookup
        self._hot_domains: Set[str] = set()
        self._cold_domains: Set[str] = set()
        self._hot_urls: Set[str] = set()
        self._cold_urls: Set[str] = set()

        # v0.4.0: Integer-based IP storage for IPv4
        self._ips_int: Set[int] = set()  # IPv4 as integers
        self._ips_str: Set[str] = set()  # IPv6 as strings
        self._hot_ips_int: Set[int] = set()
        self._cold_ips_int: Set[int] = set()
        self._hot_ips_str: Set[str] = set()
        self._cold_ips_str: Set[str] = set()

        # Metadata storage (value -> entry info)
        self._domain_meta: Dict[str, EntryMetadata] = {}
        self._url_meta: Dict[str, EntryMetadata] = {}
        self._ip_meta: Dict[str, EntryMetadata] = {}
        self._ip_int_meta: Dict[int, EntryMetadata] = {}  # Integer IP metadata

        # CIDR handling (will be initialized later if pytricia available)
        self._ipv4_cidr_tree = None
        self._ipv6_cidr_tree = None
        self._cidr_metadata: Dict[str, EntryMetadata] = {}
        self._use_pytricia = False

        # Fallback CIDR list (if pytricia not available)
        self._cidr_ranges: List[Tuple] = []

        # Thread safety
        self._lock = threading.RLock()
        self._loading = threading.Event()

        # Performance metrics
        self.metrics = StorageMetrics()

        # Initialize database and load data; fail closed on any error so a
        # broken database can never masquerade as an empty blacklist.
        try:
            self._init_db()
            self._init_cidr_trees()
            self._load_all_data()
            self._loading.set()
        except Exception as e:
            self._loading.set()
            raise RuntimeError(
                f"Cannot initialize database at {self.db_path}: {e}. Check directory permissions and disk space."
            ) from e

    def _init_db(self):
        """Initialize the SQLite database with the shared schema and PRAGMAs."""
        init_db(self.db_path)
        self.logger.info(f"Database initialized at {self.db_path}")

    def _init_cidr_trees(self):
        """Initialize CIDR radix trees if pytricia is available."""
        try:
            import pytricia
            self._ipv4_cidr_tree = pytricia.PyTricia(32)
            self._ipv6_cidr_tree = pytricia.PyTricia(128)
            self._use_pytricia = True
            self.logger.info("Using PyTricia for fast CIDR matching")
        except ImportError:
            self.logger.warning("PyTricia not available, using fallback CIDR matching (slower)")
            self._use_pytricia = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path, timeout=30.0)

    def _scratch(self):
        """Return a scratch HybridStorage with empty in-memory structures.

        Reload builds the replacement snapshot on this detached receiver —
        reusing the ``_load_*_from_db`` methods unchanged — while the live
        structures stay intact for concurrent readers. Only the swap in
        ``_load_all_data`` mutates what lookups see.
        """
        builder = object.__new__(HybridStorage)
        builder.db_path = self.db_path
        builder.logger = self.logger
        builder.metrics = self.metrics
        builder._use_pytricia = self._use_pytricia
        builder._domains = set()
        builder._urls = set()
        builder._hot_domains = set()
        builder._cold_domains = set()
        builder._hot_urls = set()
        builder._cold_urls = set()
        builder._ips_int = set()
        builder._ips_str = set()
        builder._hot_ips_int = set()
        builder._cold_ips_int = set()
        builder._hot_ips_str = set()
        builder._cold_ips_str = set()
        builder._domain_meta = {}
        builder._url_meta = {}
        builder._ip_meta = {}
        builder._ip_int_meta = {}
        builder._cidr_metadata = {}
        builder._cidr_ranges = []
        builder._ipv4_cidr_tree = None
        builder._ipv6_cidr_tree = None
        if builder._use_pytricia:
            builder._init_cidr_trees()
        return builder

    def _load_all_data(self):
        """Load all blacklist data from database into memory.

        The load runs on a scratch instance under the lock — writers keep
        serializing against reload exactly as before — and the populated
        structures are then swapped in. Readers never take the lock, so a
        lookup racing the reload sees either the complete previous snapshot
        or the complete new one: a present entry can never appear absent
        mid-reload.
        """
        start_time = time.perf_counter()
        self.logger.info("Loading blacklist data into memory (v0.4.0 optimized)...")

        with self._lock:
            builder = self._scratch()
            builder._load_domains_from_db()
            builder._load_urls_from_db()
            builder._load_ips_from_db()

            for attr in self._SNAPSHOT_ATTRS:
                setattr(self, attr, getattr(builder, attr))

        elapsed = time.perf_counter() - start_time
        total_entries = len(self._domains) + len(self._urls) + len(self._ips_int) + len(self._ips_str) + len(self._cidr_metadata)

        self.logger.info(
            f"Loaded {total_entries} entries in {elapsed:.2f}s "
            f"({len(self._domains)} domains [{len(self._hot_domains)} hot], "
            f"{len(self._urls)} URLs [{len(self._hot_urls)} hot], "
            f"{len(self._ips_int) + len(self._ips_str)} IPs "
            f"[{len(self._hot_ips_int) + len(self._hot_ips_str)} hot, {len(self._ips_int)} as int], "
            f"{len(self._cidr_metadata)} CIDRs)"
        )

        self.metrics.last_reload = datetime.now()

    def _load_domains_from_db(self):
        """Load all domains from database into memory with tiered classification."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT domain, source, date, score FROM blacklist_domain"
            )

            loaded = 0
            errors = 0

            for domain, source, date, score in cursor:
                try:
                    if not domain or not isinstance(domain, str):
                        raise ValueError("Invalid domain")

                    domain_lower = domain.lower()
                    metadata = EntryMetadata(source, date, score)

                    # Add to unified storage (backward compatibility)
                    self._domains.add(domain_lower)
                    self._domain_meta[domain_lower] = metadata

                    # v0.4.0: Add to tiered storage
                    if source in HOT_DOMAIN_SOURCES:
                        self._hot_domains.add(domain_lower)
                    else:
                        self._cold_domains.add(domain_lower)

                    loaded += 1

                except Exception as e:
                    self.logger.warning(f"Skipping invalid domain entry: {e}")
                    errors += 1

            if errors > 0:
                self.logger.info(f"Loaded {loaded} domains ({errors} errors)")
            else:
                self.logger.debug(f"Loaded {loaded} domains")

        finally:
            conn.close()

    def _load_urls_from_db(self):
        """Load all URLs from database into memory with normalization and tiering."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT url, source, date, score FROM blacklist_url"
            )

            loaded = 0
            errors = 0
            normalized_count = 0

            for url, source, date, score in cursor:
                try:
                    if not url or not isinstance(url, str):
                        raise ValueError("Invalid URL")

                    # v0.4.0: Normalize URL to reduce duplicates
                    url_normalized = normalize_url(url)
                    if url_normalized != url:
                        normalized_count += 1

                    metadata = EntryMetadata(source, date, score)

                    # Add to unified storage (backward compatibility)
                    self._urls.add(url_normalized)
                    self._url_meta[url_normalized] = metadata

                    # v0.4.0: Add to tiered storage
                    if source in HOT_URL_SOURCES:
                        self._hot_urls.add(url_normalized)
                    else:
                        self._cold_urls.add(url_normalized)

                    loaded += 1

                except Exception as e:
                    self.logger.warning(f"Skipping invalid URL entry: {e}")
                    errors += 1

            self.metrics.urls_normalized = normalized_count

            if errors > 0:
                self.logger.info(f"Loaded {loaded} URLs ({normalized_count} normalized, {errors} errors)")
            else:
                self.logger.debug(f"Loaded {loaded} URLs ({normalized_count} normalized)")

        finally:
            conn.close()

    def _load_ips_from_db(self):
        """Load all IPs and CIDR ranges with integer storage and tiering."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT ip, source, date, score FROM blacklist_ip"
            )

            loaded_ips = 0
            loaded_cidrs = 0
            errors = 0
            ips_as_int = 0

            for ip, source, date, score in cursor:
                try:
                    if not ip or not isinstance(ip, str):
                        raise ValueError("Invalid IP")

                    metadata = EntryMetadata(source, date, score)

                    if '/' in ip:
                        # CIDR range
                        if self._use_pytricia:
                            # Add to radix tree
                            if ':' in ip:  # IPv6
                                self._ipv6_cidr_tree[ip] = source
                            else:  # IPv4
                                self._ipv4_cidr_tree[ip] = source
                        else:
                            # Add to fallback list
                            try:
                                network = ipaddress.ip_network(ip, strict=False)
                                self._cidr_ranges.append((network, metadata))
                            except ValueError as e:
                                self.logger.warning(f"Invalid CIDR {ip}: {e}")
                                errors += 1
                                continue

                        self._cidr_metadata[ip] = metadata
                        loaded_cidrs += 1
                    else:
                        # Single IP - v0.4.0: Store IPv4 as integer
                        ip_int = ip_to_int(ip)

                        if ip_int is not None:
                            # IPv4 - store as integer
                            self._ips_int.add(ip_int)
                            self._ip_int_meta[ip_int] = metadata
                            ips_as_int += 1

                            # Tiered storage for IPv4
                            if source in HOT_IP_SOURCES:
                                self._hot_ips_int.add(ip_int)
                            else:
                                self._cold_ips_int.add(ip_int)
                        else:
                            # IPv6 - keep as string
                            self._ips_str.add(ip)
                            self._ip_meta[ip] = metadata

                            # Tiered storage for IPv6
                            if source in HOT_IP_SOURCES:
                                self._hot_ips_str.add(ip)
                            else:
                                self._cold_ips_str.add(ip)

                        loaded_ips += 1

                except Exception as e:
                    self.logger.warning(f"Skipping invalid IP entry: {e}")
                    errors += 1

            self.metrics.ips_as_integers = ips_as_int

            if errors > 0:
                self.logger.info(
                    f"Loaded {loaded_ips} IPs ({ips_as_int} as integers), {loaded_cidrs} CIDRs ({errors} errors)"
                )
            else:
                self.logger.debug(f"Loaded {loaded_ips} IPs ({ips_as_int} as integers), {loaded_cidrs} CIDRs")

        finally:
            conn.close()

    # ========== Fast Lookup Methods (v0.4.0 Optimized) ==========

    def is_domain_blacklisted(self, domain: str) -> bool:
        """
        Check if a domain or any parent domain is blacklisted.

        v0.4.0 optimization: Checks hot sources first for early exit.

        Performance: O(depth) where depth is number of domain levels (typically 2-5).
        All lookups are in-memory O(1) hash lookups.
        Hot source optimization provides 25-40% speedup for most lookups.

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

        domain = domain.lower()

        # v0.4.0: Check hot sources first (PhishTank, PhishStats = ~91K domains)
        if domain in self._hot_domains:
            self.metrics.hot_source_hits += 1
            self._update_metrics('domain', start, True)
            return True

        # Check parent domains in hot sources
        parts = domain.split('.')
        for i in range(1, len(parts)):
            parent = '.'.join(parts[i:])
            if parent in self._hot_domains:
                self.metrics.hot_source_hits += 1
                self._update_metrics('domain', start, True)
                return True

        # Check cold sources only if not found in hot
        if domain in self._cold_domains:
            self.metrics.cold_source_hits += 1
            self._update_metrics('domain', start, True)
            return True

        # Check parent domains in cold sources
        for i in range(1, len(parts)):
            parent = '.'.join(parts[i:])
            if parent in self._cold_domains:
                self.metrics.cold_source_hits += 1
                self._update_metrics('domain', start, True)
                return True

        self._update_metrics('domain', start, False)
        return False

    def is_url_blacklisted(self, url: str) -> bool:
        """
        Check if a URL is blacklisted (exact match with normalization).

        v0.4.0 optimizations:
        - Normalizes URL before lookup to catch variations
        - Checks hot sources first (PhishTank + URLhaus = 74% of URLs)

        Performance: O(1) hash lookup in memory.
        Hot source optimization provides 30-40% speedup.

        Args:
            url: URL to check (e.g., "http://example.com/path")

        Returns:
            True if URL is blacklisted, False otherwise
        """
        start = time.perf_counter()

        # v0.4.0: Normalize URL to catch variations
        url_normalized = normalize_url(url)

        # v0.4.0: Check hot sources first (PhishTank + URLhaus = 153K/207K URLs)
        if url_normalized in self._hot_urls:
            self.metrics.hot_source_hits += 1
            self._update_metrics('url', start, True)
            return True

        # Check cold sources only if not found in hot
        if url_normalized in self._cold_urls:
            self.metrics.cold_source_hits += 1
            self._update_metrics('url', start, True)
            return True

        self._update_metrics('url', start, False)
        return False

    def is_ip_blacklisted(self, ip: str) -> bool:
        """
        Check if an IP is blacklisted (exact match or contained in CIDR range).

        v0.4.0 optimizations:
        - Integer-based IPv4 lookups (4x smaller, faster comparison)
        - Hot source check first (BlocklistDE + CINSSCORE = 90% of IPs)

        Performance:
        - Exact match: O(1)
        - CIDR with PyTricia: O(log n)
        - Hot source optimization: 30-40% speedup

        Args:
            ip: IP address to check (e.g., "192.168.1.1" or "2001:db8::1")

        Returns:
            True if IP is blacklisted, False otherwise
        """
        start = time.perf_counter()

        # v0.4.0: Convert IPv4 to integer for fast lookup
        ip_int = ip_to_int(ip)

        if ip_int is not None:
            # IPv4 - check as integer (hot sources first)
            if ip_int in self._hot_ips_int:
                self.metrics.hot_source_hits += 1
                self._update_metrics('ip', start, True)
                return True

            if ip_int in self._cold_ips_int:
                self.metrics.cold_source_hits += 1
                self._update_metrics('ip', start, True)
                return True
        else:
            # Not a parseable IPv4 — reject malformed input before it can be
            # treated as an IPv6 string or reach the radix trees, where
            # pytricia raises SystemError on unparseable keys.
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                self._update_metrics('ip', start, False)
                return False

            # IPv6 - check as string (hot sources first)
            if ip in self._hot_ips_str:
                self.metrics.hot_source_hits += 1
                self._update_metrics('ip', start, True)
                return True

            if ip in self._cold_ips_str:
                self.metrics.cold_source_hits += 1
                self._update_metrics('ip', start, True)
                return True

        # Check CIDR ranges (if not exact match)
        if self._use_pytricia:
            # Fast radix tree lookup
            try:
                if ':' in ip:  # IPv6
                    result = ip in self._ipv6_cidr_tree
                else:  # IPv4
                    result = ip in self._ipv4_cidr_tree
                self._update_metrics('ip', start, result)
                return result
            except (KeyError, ValueError):
                self._update_metrics('ip', start, False)
                return False
        else:
            # Fallback: linear scan through CIDR ranges
            try:
                addr = ipaddress.ip_address(ip)
                for network, _ in self._cidr_ranges:
                    if addr in network:
                        self._update_metrics('ip', start, True)
                        return True
            except ValueError:
                pass

        self._update_metrics('ip', start, False)
        return False

    def _update_metrics(self, lookup_type: str, start_time: float, found: bool):
        """Update performance metrics."""
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        self.metrics.total_lookups += 1

        if lookup_type == 'domain':
            self.metrics.domain_lookups += 1
        elif lookup_type == 'url':
            self.metrics.url_lookups += 1
        elif lookup_type == 'ip':
            self.metrics.ip_lookups += 1

        if found:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1

        # Update running average
        if self.metrics.total_lookups == 1:
            self.metrics.avg_lookup_time_ms = elapsed_ms
        else:
            self.metrics.avg_lookup_time_ms = (
                (self.metrics.avg_lookup_time_ms * (self.metrics.total_lookups - 1) + elapsed_ms)
                / self.metrics.total_lookups
            )

    # ========== Metadata Retrieval Methods ==========

    def get_domain_blacklist_source(self, domain: str) -> Optional[str]:
        """
        Get the source that blacklisted a domain (including parent domains).

        Args:
            domain: Domain to check

        Returns:
            Source name if blacklisted, None otherwise
        """
        domain = domain.lower()

        # Check exact match
        if domain in self._domain_meta:
            return self._domain_meta[domain].source

        # Check parent domains
        parts = domain.split('.')
        for i in range(1, len(parts)):
            parent = '.'.join(parts[i:])
            if parent in self._domain_meta:
                return self._domain_meta[parent].source

        return None

    def get_url_blacklist_source(self, url: str) -> Optional[str]:
        """
        Get the source that blacklisted a URL (with normalization).

        Args:
            url: URL to check

        Returns:
            Source name if blacklisted, None otherwise
        """
        url_normalized = normalize_url(url)
        metadata = self._url_meta.get(url_normalized)
        return metadata.source if metadata else None

    def get_ip_blacklist_source(self, ip: str) -> Optional[str]:
        """
        Get the source that blacklisted an IP (exact match or CIDR).

        Args:
            ip: IP address to check

        Returns:
            Source name if blacklisted, None otherwise
        """
        # Check integer IPv4 first
        ip_int = ip_to_int(ip)
        if ip_int is not None:
            metadata = self._ip_int_meta.get(ip_int)
            if metadata:
                return metadata.source
        else:
            # Reject malformed input: an unparseable key raises SystemError
            # in the pytricia lookups below instead of returning None.
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                return None

        # Check string IP (IPv6 or fallback)
        metadata = self._ip_meta.get(ip)
        if metadata:
            return metadata.source

        # Check CIDR ranges
        if self._use_pytricia:
            try:
                if ':' in ip:  # IPv6
                    return self._ipv6_cidr_tree.get(ip)
                else:  # IPv4
                    return self._ipv4_cidr_tree.get(ip)
            except (KeyError, ValueError):
                return None
        else:
            # Fallback: find matching CIDR
            try:
                addr = ipaddress.ip_address(ip)
                for network, metadata in self._cidr_ranges:
                    if addr in network:
                        return metadata.source
            except ValueError:
                pass

        return None

    # ========== Write Operations (Dual Write) ==========

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
            metadata = EntryMetadata(source, date, score)

            # Update memory first
            self._domains.add(domain_lower)
            self._domain_meta[domain_lower] = metadata

            # v0.4.0: Add to tiered storage
            if source in HOT_DOMAIN_SOURCES:
                self._hot_domains.add(domain_lower)
            else:
                self._cold_domains.add(domain_lower)

            # Persist to database
            try:
                conn = self._get_connection()
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                        (domain, date, score, source)
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception as e:
                # Rollback memory changes on DB failure
                self._domains.discard(domain_lower)
                self._domain_meta.pop(domain_lower, None)
                self._hot_domains.discard(domain_lower)
                self._cold_domains.discard(domain_lower)
                self.logger.error(f"Failed to add domain to database: {e}")
                raise

    def add_url(self, url: str, date: str, score: float, source: str):
        """Add a URL to both memory and database with normalization."""
        with self._lock:
            # v0.4.0: Normalize URL
            url_normalized = normalize_url(url)
            metadata = EntryMetadata(source, date, score)

            # Update memory first
            self._urls.add(url_normalized)
            self._url_meta[url_normalized] = metadata

            # v0.4.0: Add to tiered storage
            if source in HOT_URL_SOURCES:
                self._hot_urls.add(url_normalized)
            else:
                self._cold_urls.add(url_normalized)

            # Persist to database (store original for compatibility)
            try:
                conn = self._get_connection()
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                        (url, date, score, source)
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception as e:
                # Rollback
                self._urls.discard(url_normalized)
                self._url_meta.pop(url_normalized, None)
                self._hot_urls.discard(url_normalized)
                self._cold_urls.discard(url_normalized)
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

            metadata = EntryMetadata(source, date, score)

            # Determine if CIDR or single IP
            is_cidr = '/' in ip

            # Update memory first
            if is_cidr:
                try:
                    if self._use_pytricia:
                        if ':' in ip:  # IPv6
                            self._ipv6_cidr_tree[ip] = source
                        else:  # IPv4
                            self._ipv4_cidr_tree[ip] = source
                    else:
                        network = ipaddress.ip_network(ip, strict=False)
                        self._cidr_ranges.append((network, metadata))
                except (ValueError, SystemError) as e:
                    # Surface every rejection as ValueError — pytricia raises
                    # SystemError on keys it cannot store.
                    self.logger.error(f"Invalid CIDR {ip}: {e}")
                    raise ValueError(f"Invalid CIDR {ip}: {e}") from e

                self._cidr_metadata[ip] = metadata
            else:
                # v0.4.0: Store IPv4 as integer
                ip_int = ip_to_int(ip)

                if ip_int is not None:
                    self._ips_int.add(ip_int)
                    self._ip_int_meta[ip_int] = metadata

                    if source in HOT_IP_SOURCES:
                        self._hot_ips_int.add(ip_int)
                    else:
                        self._cold_ips_int.add(ip_int)
                else:
                    self._ips_str.add(ip)
                    self._ip_meta[ip] = metadata

                    if source in HOT_IP_SOURCES:
                        self._hot_ips_str.add(ip)
                    else:
                        self._cold_ips_str.add(ip)

            # Persist to database
            try:
                conn = self._get_connection()
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                        (ip, date, score, source)
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception as e:
                # Rollback
                if is_cidr:
                    self._cidr_metadata.pop(ip, None)
                else:
                    if ip_int is not None:
                        self._ips_int.discard(ip_int)
                        self._ip_int_meta.pop(ip_int, None)
                        self._hot_ips_int.discard(ip_int)
                        self._cold_ips_int.discard(ip_int)
                    else:
                        self._ips_str.discard(ip)
                        self._ip_meta.pop(ip, None)
                        self._hot_ips_str.discard(ip)
                        self._cold_ips_str.discard(ip)
                self.logger.error(f"Failed to add IP to database: {e}")
                raise

    def add_domains(self, domains: List[Tuple[str, str, float, str]]):
        """Add multiple domains efficiently (batch operation)."""
        with self._lock:
            # Update memory
            for domain, date, score, source in domains:
                domain_lower = domain.lower()
                metadata = EntryMetadata(source, date, score)
                self._domains.add(domain_lower)
                self._domain_meta[domain_lower] = metadata

                # v0.4.0: Tiered storage
                if source in HOT_DOMAIN_SOURCES:
                    self._hot_domains.add(domain_lower)
                else:
                    self._cold_domains.add(domain_lower)

            # Persist to database in transaction
            conn = self._get_connection()
            try:
                conn.executemany(
                    "INSERT OR REPLACE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                    domains
                )
                conn.commit()
            except Exception as e:
                self.logger.error(f"Failed to add domains batch: {e}")
                # Reload from DB to ensure consistency
                self._load_domains_from_db()
                raise
            finally:
                conn.close()

    def add_urls(self, urls: List[Tuple[str, str, float, str]]):
        """Add multiple URLs efficiently (batch operation with normalization)."""
        with self._lock:
            # Update memory
            for url, date, score, source in urls:
                url_normalized = normalize_url(url)
                metadata = EntryMetadata(source, date, score)
                self._urls.add(url_normalized)
                self._url_meta[url_normalized] = metadata

                # v0.4.0: Tiered storage
                if source in HOT_URL_SOURCES:
                    self._hot_urls.add(url_normalized)
                else:
                    self._cold_urls.add(url_normalized)

            # Persist to database
            conn = self._get_connection()
            try:
                conn.executemany(
                    "INSERT OR REPLACE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                    urls
                )
                conn.commit()
            except Exception as e:
                self.logger.error(f"Failed to add URLs batch: {e}")
                self._load_urls_from_db()
                raise
            finally:
                conn.close()

    def add_ips(self, ips: List[Tuple[str, str, float, str]]):
        """Add multiple IPs efficiently (batch operation with integer storage)."""
        with self._lock:
            # Update memory — and collect only the entries that validate, so
            # skipped input can never drift between memory and the database.
            persist = []
            for ip, date, score, source in ips:
                metadata = EntryMetadata(source, date, score)

                if '/' in ip:  # CIDR
                    # Skip networks the parser or radix tree rejects
                    # (pytricia raises SystemError on unparseable keys).
                    try:
                        network = ipaddress.ip_network(ip, strict=False)
                        if self._use_pytricia:
                            if ':' in ip:
                                self._ipv6_cidr_tree[ip] = source
                            else:
                                self._ipv4_cidr_tree[ip] = source
                        else:
                            self._cidr_ranges.append((network, metadata))
                    except (ValueError, SystemError):
                        continue
                    self._cidr_metadata[ip] = metadata
                else:  # Single IP
                    ip_int = ip_to_int(ip)

                    if ip_int is not None:
                        self._ips_int.add(ip_int)
                        self._ip_int_meta[ip_int] = metadata

                        if source in HOT_IP_SOURCES:
                            self._hot_ips_int.add(ip_int)
                        else:
                            self._cold_ips_int.add(ip_int)
                    else:
                        # Skip invalid input — an unparseable IPv4 is not an
                        # IPv6 address and must not be stored as one.
                        try:
                            ipaddress.ip_address(ip)
                        except ValueError:
                            continue
                        self._ips_str.add(ip)
                        self._ip_meta[ip] = metadata

                        if source in HOT_IP_SOURCES:
                            self._hot_ips_str.add(ip)
                        else:
                            self._cold_ips_str.add(ip)

                persist.append((ip, date, score, source))

            # Persist to database
            conn = self._get_connection()
            try:
                conn.executemany(
                    "INSERT OR REPLACE INTO blacklist_ip (ip, date, score, source) VALUES (?, ?, ?, ?)",
                    persist
                )
                conn.commit()
            except Exception as e:
                self.logger.error(f"Failed to add IPs batch: {e}")
                self._load_ips_from_db()
                raise
            finally:
                conn.close()

    def add_entries(self, entries: List[Tuple[str, Optional[str], str, float, str]]):
        """
        Add entries from blacklist updater (legacy compatibility).

        Args:
            entries: List of (url, ip, date, score, source) tuples
        """
        domains_to_add = []
        urls_to_add = []
        ips_to_add = []

        for url_val, ip_val, date_val, score_val, source in entries:
            if ip_val:
                ips_to_add.append((ip_val, date_val, score_val, source))

            if url_val:
                # Determine if it's a domain-only URL or a full URL
                if url_val.startswith(('http://', 'https://')):
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(url_val)
                        domain = parsed.netloc
                        is_domain_entry = not parsed.path or parsed.path == '/'

                        if is_domain_entry and domain:
                            domains_to_add.append((domain, date_val, score_val, source))
                        else:
                            urls_to_add.append((url_val, date_val, score_val, source))
                    except:
                        pass

        if domains_to_add:
            self.add_domains(domains_to_add)
        if urls_to_add:
            self.add_urls(urls_to_add)
        if ips_to_add:
            self.add_ips(ips_to_add)

    # ========== Statistics & Query Methods ==========

    def count_entries(self) -> int:
        """Get total count of all entries (instant from memory)."""
        return len(self._domains) + len(self._urls) + len(self._ips_int) + len(self._ips_str) + len(self._cidr_metadata)

    def get_source_counts(self) -> Dict[str, int]:
        """Count entries per source from memory."""
        counts: Dict[str, int] = {}

        # Count domains
        for meta in self._domain_meta.values():
            counts[meta.source] = counts.get(meta.source, 0) + 1

        # Count URLs
        for meta in self._url_meta.values():
            counts[meta.source] = counts.get(meta.source, 0) + 1

        # Count IPs (string)
        for meta in self._ip_meta.values():
            counts[meta.source] = counts.get(meta.source, 0) + 1

        # Count IPs (integer)
        for meta in self._ip_int_meta.values():
            counts[meta.source] = counts.get(meta.source, 0) + 1

        # Count CIDRs
        for meta in self._cidr_metadata.values():
            counts[meta.source] = counts.get(meta.source, 0) + 1

        return counts

    def get_source_type_counts(self) -> Dict[str, dict]:
        """Get breakdown of domain/url/ip entries per source."""
        stats: Dict[str, dict] = {}

        # Domains
        for meta in self._domain_meta.values():
            if meta.source not in stats:
                stats[meta.source] = {"domain": 0, "url": 0, "ip": 0}
            stats[meta.source]["domain"] += 1

        # URLs
        for meta in self._url_meta.values():
            if meta.source not in stats:
                stats[meta.source] = {"domain": 0, "url": 0, "ip": 0}
            stats[meta.source]["url"] += 1

        # IPs (string and int) and CIDRs
        for meta in self._ip_meta.values():
            if meta.source not in stats:
                stats[meta.source] = {"domain": 0, "url": 0, "ip": 0}
            stats[meta.source]["ip"] += 1

        for meta in self._ip_int_meta.values():
            if meta.source not in stats:
                stats[meta.source] = {"domain": 0, "url": 0, "ip": 0}
            stats[meta.source]["ip"] += 1

        for meta in self._cidr_metadata.values():
            if meta.source not in stats:
                stats[meta.source] = {"domain": 0, "url": 0, "ip": 0}
            stats[meta.source]["ip"] += 1

        return stats

    def get_active_sources(self) -> List[str]:
        """Get list of active sources."""
        sources = set()
        sources.update(meta.source for meta in self._domain_meta.values())
        sources.update(meta.source for meta in self._url_meta.values())
        sources.update(meta.source for meta in self._ip_meta.values())
        sources.update(meta.source for meta in self._ip_int_meta.values())
        sources.update(meta.source for meta in self._cidr_metadata.values())
        return list(sources)

    def sample_entries(self, count: int = 10) -> List[str]:
        """Return a random sample of entries.

        Reservoir sampling over the in-memory pools: uniform selection with
        O(count) extra space, so sampling never materializes a list of all
        entries even on a multi-hundred-thousand-entry store.
        """
        if count <= 0:
            return []
        reservoir: List[str] = []
        seen = 0
        with self._lock:
            pools = itertools.chain(
                self._domains,
                self._urls,
                (int_to_ip(ip_int) for ip_int in self._ips_int),
                self._ips_str,
                self._cidr_metadata,
            )
            for entry in pools:
                seen += 1
                if len(reservoir) < count:
                    reservoir.append(entry)
                else:
                    slot = random.randrange(seen)
                    if slot < count:
                        reservoir[slot] = entry
        return reservoir

    def get_last_update(self) -> datetime:
        """Get timestamp of last update from database."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT MAX(timestamp) FROM updates")
            result = cursor.fetchone()[0]
            return datetime.fromisoformat(result) if result else datetime.min
        finally:
            conn.close()

    def get_last_update_per_source(self) -> Dict[str, str]:
        """Get last update timestamp for each source."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT source, MAX(timestamp) FROM updates GROUP BY source"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_update_history(self, source: str = None, start: str = None, end: str = None) -> list:
        """Return update history records from database."""
        conn = self._get_connection()
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

    def log_update(self, source: str, entry_count: int):
        """Log an update to the database."""
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT INTO updates (source, entry_count) VALUES (?, ?)",
                (source, entry_count)
            )
            conn.commit()
        finally:
            conn.close()

    # ========== Utility Methods ==========

    def flush_cache(self) -> bool:
        """Reload all data from database (equivalent to cache flush)."""
        self.logger.info("Flushing cache (reloading from database)...")
        try:
            self._load_all_data()
            return True
        except Exception as e:
            self.logger.error(f"Failed to flush cache: {e}")
            return False

    def reload(self):
        """Reload all data from database."""
        self._load_all_data()

    def remove_entry(self, value: str) -> bool:
        """Remove an entry from both memory and database."""
        with self._lock:
            removed = False

            # Try to remove from all types
            if value.lower() in self._domains:
                self._domains.discard(value.lower())
                self._domain_meta.pop(value.lower(), None)
                self._hot_domains.discard(value.lower())
                self._cold_domains.discard(value.lower())
                removed = True

            value_normalized = normalize_url(value)
            if value_normalized in self._urls:
                self._urls.discard(value_normalized)
                self._url_meta.pop(value_normalized, None)
                self._hot_urls.discard(value_normalized)
                self._cold_urls.discard(value_normalized)
                removed = True

            # Try IP as string (IPv6)
            if value in self._ips_str:
                self._ips_str.discard(value)
                self._ip_meta.pop(value, None)
                self._hot_ips_str.discard(value)
                self._cold_ips_str.discard(value)
                removed = True

            # Try IP as integer (IPv4)
            ip_int = ip_to_int(value)
            if ip_int is not None and ip_int in self._ips_int:
                self._ips_int.discard(ip_int)
                self._ip_int_meta.pop(ip_int, None)
                self._hot_ips_int.discard(ip_int)
                self._cold_ips_int.discard(ip_int)
                removed = True

            if value in self._cidr_metadata:
                self._cidr_metadata.pop(value, None)
                # Drop the range from the live matcher too — metadata alone
                # would leave member IPs blacklisted until the next reload.
                if self._use_pytricia:
                    tree = self._ipv6_cidr_tree if ':' in value else self._ipv4_cidr_tree
                    try:
                        del tree[value]
                    except KeyError:
                        pass
                else:
                    try:
                        removed_net = ipaddress.ip_network(value, strict=False)
                        self._cidr_ranges = [
                            (net, meta) for net, meta in self._cidr_ranges if net != removed_net
                        ]
                    except ValueError:
                        pass
                removed = True

            if removed:
                # Remove from database
                conn = self._get_connection()
                try:
                    conn.execute("DELETE FROM blacklist_domain WHERE domain = ?", (value,))
                    conn.execute("DELETE FROM blacklist_url WHERE url = ?", (value,))
                    conn.execute("DELETE FROM blacklist_ip WHERE ip = ?", (value,))
                    conn.commit()
                finally:
                    conn.close()

            return removed

    def get_metrics(self) -> dict:
        """Get current storage performance metrics (v0.4.0 enhanced)."""
        try:
            import psutil
            process = psutil.Process()
            self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        except (ImportError, Exception):
            self.metrics.memory_usage_mb = 0.0

        total_lookups = self.metrics.total_lookups
        hot_hit_rate = (self.metrics.hot_source_hits / total_lookups * 100) if total_lookups > 0 else 0

        return {
            "total_lookups": total_lookups,
            "domain_lookups": self.metrics.domain_lookups,
            "url_lookups": self.metrics.url_lookups,
            "ip_lookups": self.metrics.ip_lookups,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "hit_rate": self.metrics.cache_hits / total_lookups if total_lookups > 0 else 0,
            "avg_lookup_time_ms": f"{self.metrics.avg_lookup_time_ms:.4f}",
            "memory_usage_mb": f"{self.metrics.memory_usage_mb:.1f}",
            "last_reload": self.metrics.last_reload.isoformat() if self.metrics.last_reload else None,
            "entry_count": self.count_entries(),
            "using_pytricia": self._use_pytricia,
            # v0.4.0 optimization metrics
            "hot_source_hits": self.metrics.hot_source_hits,
            "cold_source_hits": self.metrics.cold_source_hits,
            "hot_hit_rate_pct": f"{hot_hit_rate:.1f}",
            "urls_normalized": self.metrics.urls_normalized,
            "ips_as_integers": self.metrics.ips_as_integers,
            "optimization_version": "0.4.0"
        }
