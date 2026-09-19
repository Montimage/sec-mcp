"""In-memory index layer for HybridStorage (v0.4.0).

``EntryIndex`` owns every in-memory structure the hybrid backend consults —
the per-type sets, the metadata maps and the CIDR matcher — together with
the membership checks, source attribution, mutations and database-row loads
that keep them consistent. ``HybridStorage`` composes exactly one index and
replaces it atomically on reload, so a lookup always observes a complete
snapshot: the previous index or the new one, never a half-populated mix.

Keys are canonical by the time they reach the index: domains are lowercased
and URLs are normalized by the caller. IPv4 addresses are stored as integers
(``_ips_int``/``_ip_int_meta``), IPv6 addresses and CIDR ranges as strings.
"""

import ipaddress
import itertools
import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

try:
    from .storage_base import normalize_url
except ImportError:
    # Direct file load (e.g. benchmark.py's spec_from_file_location) has no
    # package context for a relative import.
    from sec_mcp.storage_base import normalize_url

logger = logging.getLogger("sec_mcp.storage_v2")


@dataclass
class EntryMetadata:
    """Metadata for a blacklist entry."""
    source: str
    date: str
    score: float


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
        # Reject anything int() parses that a real IPv4 octet cannot be:
        # out-of-range values ("1.2.3.999" sums to the same integer as
        # "1.2.6.231") and non-canonical spellings ("+1", " 1", "01") that
        # alias a different, real address — and that pytricia later rejects
        # with SystemError when the raw string reaches the radix tree.
        if any(
            str(octet) != part or octet < 0 or octet > 255
            for octet, part in zip(octets, parts)
        ):
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


class CidrIndex:
    """The CIDR-range half of the entry index.

    Ranges match through pytricia radix trees when available (O(log n)) and
    through a linear ``_cidr_ranges`` scan otherwise; ``_cidr_metadata`` maps
    each range string to its ``EntryMetadata`` either way.
    """

    def __init__(self):
        self._ipv4_cidr_tree = None
        self._ipv6_cidr_tree = None
        self._cidr_metadata: Dict[str, EntryMetadata] = {}
        # Fallback CIDR list (if pytricia not available)
        self._cidr_ranges: List[Tuple] = []
        self._use_pytricia = False
        self._init_cidr_trees()

    def _init_cidr_trees(self):
        """Initialize CIDR radix trees if pytricia is available."""
        try:
            import pytricia
            self._ipv4_cidr_tree = pytricia.PyTricia(32)
            self._ipv6_cidr_tree = pytricia.PyTricia(128)
            self._use_pytricia = True
            logger.info("Using PyTricia for fast CIDR matching")
        except ImportError:
            logger.warning("PyTricia not available, using fallback CIDR matching (slower)")
            self._use_pytricia = False

    def empty_like(self) -> "CidrIndex":
        """A fresh empty matcher using the same backend as this one.

        Reload builds the replacement snapshot on this detached index so the
        live matcher stays intact for concurrent readers until the swap.
        """
        idx = CidrIndex.__new__(CidrIndex)
        idx._ipv4_cidr_tree = None
        idx._ipv6_cidr_tree = None
        idx._cidr_metadata = {}
        idx._cidr_ranges = []
        idx._use_pytricia = self._use_pytricia
        if idx._use_pytricia:
            idx._init_cidr_trees()
        return idx

    def has_range(self, value: str) -> bool:
        """Whether ``value`` names a stored CIDR range."""
        return value in self._cidr_metadata

    def has(self, ip: str) -> bool:
        """CIDR-membership check: radix tree, or linear fallback scan."""
        if self._use_pytricia:
            try:
                if ':' in ip:  # IPv6
                    return ip in self._ipv6_cidr_tree
                return ip in self._ipv4_cidr_tree
            except (KeyError, ValueError, SystemError):
                # pytricia raises SystemError on keys it cannot parse —
                # a malformed lookup must return False, not crash.
                return False
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for network, _ in self._cidr_ranges:
            if addr in network:
                return True
        return False

    def source(self, ip: str) -> Optional[str]:
        """Source attribution for an IP matched by a range, or None."""
        if self._use_pytricia:
            try:
                if ':' in ip:  # IPv6
                    return self._ipv6_cidr_tree.get(ip)
                return self._ipv4_cidr_tree.get(ip)
            except (KeyError, ValueError, SystemError):
                return None
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        for network, metadata in self._cidr_ranges:
            if addr in network:
                return metadata.source
        return None

    def _insert(self, ip: str, source: str, metadata: EntryMetadata) -> None:
        """Route one range into the live matcher (tree or fallback list)."""
        if self._use_pytricia:
            if ':' in ip:  # IPv6
                self._ipv6_cidr_tree[ip] = source
            else:  # IPv4
                self._ipv4_cidr_tree[ip] = source
        else:
            network = ipaddress.ip_network(ip, strict=False)
            self._cidr_ranges.append((network, metadata))

    def add(self, ip: str, source: str, metadata: EntryMetadata) -> None:
        """Insert a validated range; rejection surfaces as ValueError."""
        try:
            self._insert(ip, source, metadata)
        except (ValueError, SystemError) as e:
            # Surface every rejection as ValueError — pytricia raises
            # SystemError on keys it cannot store.
            logger.error(f"Invalid CIDR {ip}: {e}")
            raise ValueError(f"Invalid CIDR {ip}: {e}") from e
        self._cidr_metadata[ip] = metadata

    def try_add(self, ip: str, source: str, metadata: EntryMetadata) -> bool:
        """Batch insert: validate and insert, silently skipping rejects."""
        try:
            ipaddress.ip_network(ip, strict=False)
            self._insert(ip, source, metadata)
        except (ValueError, SystemError):
            # Skip networks the parser or radix tree rejects (pytricia
            # raises SystemError on unparseable keys).
            return False
        self._cidr_metadata[ip] = metadata
        return True

    def load(self, ip: str, metadata: EntryMetadata) -> int:
        """Load one range from a database row: 1 stored, 0 rejected."""
        if self._use_pytricia:
            # Tree insert errors propagate to the row loop's handler.
            self._insert(ip, metadata.source, metadata)
        else:
            try:
                network = ipaddress.ip_network(ip, strict=False)
                self._cidr_ranges.append((network, metadata))
            except ValueError as e:
                logger.warning(f"Invalid CIDR {ip}: {e}")
                return 0
        self._cidr_metadata[ip] = metadata
        return 1

    def remove(self, value: str) -> None:
        """Drop a range's metadata and its live matcher entry.

        Removing the metadata alone would leave member IPs blacklisted
        until the next reload.
        """
        self._cidr_metadata.pop(value, None)
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

    def discard(self, value: str) -> None:
        """Rollback-side removal — metadata only, matching add()'s undo."""
        self._cidr_metadata.pop(value, None)

    def count(self) -> int:
        return len(self._cidr_metadata)

    def metadata_values(self):
        return self._cidr_metadata.values()

    def keys(self):
        return self._cidr_metadata.keys()


class IndexMutationMixin:
    """Memory-side mutations: single inserts, batch inserts and removal.

    Every method mirrors a persistence write in
    :class:`sec_mcp.storage_v2_writes.DualWriteMixin` — the database row
    lands first, then these update the in-memory pools, with the
    ``discard_*`` methods rolling the memory side back on DB failure.
    """

    def add_domain(self, domain_lower: str, metadata: EntryMetadata) -> None:
        """Insert a pre-lowercased domain into memory."""
        self._domains.add(domain_lower)
        self._domain_meta[domain_lower] = metadata

    def discard_domain(self, domain_lower: str) -> None:
        """Undo ``add_domain`` — the rollback path on database failure."""
        self._domains.discard(domain_lower)
        self._domain_meta.pop(domain_lower, None)

    def add_url(self, url_normalized: str, metadata: EntryMetadata) -> None:
        """Insert a canonical URL into memory."""
        self._urls.add(url_normalized)
        self._url_meta[url_normalized] = metadata

    def discard_url(self, url_normalized: str) -> None:
        """Undo ``add_url`` — the rollback path on database failure."""
        self._urls.discard(url_normalized)
        self._url_meta.pop(url_normalized, None)

    def add_ip(self, ip: str, source: str, metadata: EntryMetadata) -> None:
        """Insert a validated IP or CIDR into memory (raises ValueError)."""
        if '/' in ip:
            self._cidr.add(ip, source, metadata)
            return
        # v0.4.0: Store IPv4 as integer
        ip_int = ip_to_int(ip)
        if ip_int is not None:
            self._ips_int.add(ip_int)
            self._ip_int_meta[ip_int] = metadata
        else:
            self._ips_str.add(ip)
            self._ip_meta[ip] = metadata

    def discard_ip(self, ip: str, is_cidr: bool, ip_int: Optional[int]) -> None:
        """Undo ``add_ip`` — the rollback path on database failure."""
        if is_cidr:
            self._cidr.discard(ip)
        elif ip_int is not None:
            self._ips_int.discard(ip_int)
            self._ip_int_meta.pop(ip_int, None)
        else:
            self._ips_str.discard(ip)
            self._ip_meta.pop(ip, None)

    def add_domains(self, domains) -> None:
        """Insert ``(domain, date, score, source)`` rows into memory."""
        for domain, date, score, source in domains:
            domain_lower = domain.lower()
            self._domains.add(domain_lower)
            self._domain_meta[domain_lower] = EntryMetadata(source, date, score)

    def add_urls(self, urls) -> list:
        """Insert normalized URLs; returns the canonical rows to persist."""
        normalized_rows = []
        for url, date, score, source in urls:
            url_normalized = normalize_url(url)
            self._urls.add(url_normalized)
            self._url_meta[url_normalized] = EntryMetadata(source, date, score)
            normalized_rows.append((url_normalized, date, score, source))
        return normalized_rows

    def add_ips(self, ips) -> list:
        """Insert valid IPs; returns the rows to persist (invalid skipped)."""
        persist = []
        for ip, date, score, source in ips:
            metadata = EntryMetadata(source, date, score)
            if self._add_ip_if_valid(ip, source, metadata):
                persist.append((ip, date, score, source))
        return persist

    def _add_ip_if_valid(self, ip: str, source: str, metadata: EntryMetadata) -> bool:
        """Insert one batch IP/CIDR; False when the input is rejected."""
        if '/' in ip:  # CIDR
            return self._cidr.try_add(ip, source, metadata)
        ip_int = ip_to_int(ip)
        if ip_int is not None:
            self._ips_int.add(ip_int)
            self._ip_int_meta[ip_int] = metadata
            return True
        # Skip invalid input — an unparseable IPv4 is not an IPv6 address
        # and must not be stored as one.
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return False
        self._ips_str.add(ip)
        self._ip_meta[ip] = metadata
        return True

    def remove(self, value: str, value_normalized: str) -> bool:
        """Drop ``value`` from every pool it occupies; True if any removed."""
        removed = False
        if value.lower() in self._domains:
            self._domains.discard(value.lower())
            self._domain_meta.pop(value.lower(), None)
            removed = True
        if value_normalized in self._urls:
            self._urls.discard(value_normalized)
            self._url_meta.pop(value_normalized, None)
            removed = True
        # Try IP as string (IPv6)
        if value in self._ips_str:
            self._ips_str.discard(value)
            self._ip_meta.pop(value, None)
            removed = True
        # Try IP as integer (IPv4)
        ip_int = ip_to_int(value)
        if ip_int is not None and ip_int in self._ips_int:
            self._ips_int.discard(ip_int)
            self._ip_int_meta.pop(ip_int, None)
            removed = True
        if self._cidr.has_range(value):
            self._cidr.remove(value)
            removed = True
        return removed


class IndexAggregatesMixin:
    """Read-only aggregates over the pools: counts, per-source stats, samples."""

    def count(self) -> int:
        """Total entries across every pool."""
        return (
            len(self._domains) + len(self._urls)
            + len(self._ips_int) + len(self._ips_str)
            + self._cidr.count()
        )

    def _all_metadata(self):
        """Every metadata record across the per-type pools and CIDRs."""
        return itertools.chain(
            self._domain_meta.values(),
            self._url_meta.values(),
            self._ip_meta.values(),
            self._ip_int_meta.values(),
            self._cidr.metadata_values(),
        )

    def source_counts(self) -> Dict[str, int]:
        """Entry count per source across all pools."""
        counts: Dict[str, int] = {}
        for meta in self._all_metadata():
            counts[meta.source] = counts.get(meta.source, 0) + 1
        return counts

    def source_type_counts(self) -> Dict[str, dict]:
        """Breakdown of domain/url/ip entries per source."""
        stats: Dict[str, dict] = {}
        for meta in self._domain_meta.values():
            stats.setdefault(meta.source, {"domain": 0, "url": 0, "ip": 0})["domain"] += 1
        for meta in self._url_meta.values():
            stats.setdefault(meta.source, {"domain": 0, "url": 0, "ip": 0})["url"] += 1
        for meta in itertools.chain(
            self._ip_meta.values(),
            self._ip_int_meta.values(),
            self._cidr.metadata_values(),
        ):
            stats.setdefault(meta.source, {"domain": 0, "url": 0, "ip": 0})["ip"] += 1
        return stats

    def active_sources(self) -> List[str]:
        """Every source that contributed at least one entry."""
        return list({meta.source for meta in self._all_metadata()})

    def sample(self, count: int) -> List[str]:
        """Reservoir-sample ``count`` entries — O(count) space, no full list."""
        if count <= 0:
            return []
        reservoir: List[str] = []
        seen = 0
        pools = itertools.chain(
            self._domains,
            self._urls,
            (int_to_ip(ip_int) for ip_int in self._ips_int),
            self._ips_str,
            self._cidr.keys(),
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


class EntryIndex(IndexMutationMixin, IndexAggregatesMixin):
    """The in-memory half of HybridStorage: sets, maps and the CIDR matcher.

    One index per entry type: ``_domains`` for domains, ``_urls`` for URLs,
    ``_ips_int``/``_ips_str`` for IPv4/IPv6 single addresses and ``_cidr``
    for ranges. Every structure a (re)load replaces lives here, so swapping
    the index object swaps the whole snapshot atomically. Mutations come
    from :class:`IndexMutationMixin`, aggregates from
    :class:`IndexAggregatesMixin`; this half keeps construction, snapshot
    cloning, database-row loads, membership checks and source attribution.
    """

    def __init__(self):
        # v0.4.0: Integer-based IP storage for IPv4
        self._domains: Set[str] = set()
        self._urls: Set[str] = set()
        self._ips_int: Set[int] = set()  # IPv4 as integers
        self._ips_str: Set[str] = set()  # IPv6 as strings

        # Metadata storage (value -> entry info)
        self._domain_meta: Dict[str, EntryMetadata] = {}
        self._url_meta: Dict[str, EntryMetadata] = {}
        self._ip_meta: Dict[str, EntryMetadata] = {}
        self._ip_int_meta: Dict[int, EntryMetadata] = {}  # Integer IP metadata

        self._cidr = CidrIndex()

    def empty_like(self) -> "EntryIndex":
        """A fresh empty index using the same CIDR backend as this one.

        Reload builds the replacement snapshot on this detached index so the
        live structures stay intact for concurrent readers until the swap.
        """
        idx = EntryIndex.__new__(EntryIndex)
        idx._domains = set()
        idx._urls = set()
        idx._ips_int = set()
        idx._ips_str = set()
        idx._domain_meta = {}
        idx._url_meta = {}
        idx._ip_meta = {}
        idx._ip_int_meta = {}
        idx._cidr = self._cidr.empty_like()
        return idx

    # ========== Loads (rows come from SQLiteStore iterators) ==========

    def load_domains(self, rows) -> int:
        """Load all domain rows into memory; returns the loaded count."""
        loaded = 0
        errors = 0
        for domain, source, date, score in rows:
            try:
                if not domain or not isinstance(domain, str):
                    raise ValueError("Invalid domain")
                domain_lower = domain.lower()
                self._domains.add(domain_lower)
                self._domain_meta[domain_lower] = EntryMetadata(source, date, score)
                loaded += 1
            except Exception as e:
                logger.warning(f"Skipping invalid domain entry: {e}")
                errors += 1
        if errors > 0:
            logger.info(f"Loaded {loaded} domains ({errors} errors)")
        else:
            logger.debug(f"Loaded {loaded} domains")
        return loaded

    def load_urls(self, rows) -> int:
        """Load all URL rows with normalization; returns the normalized count."""
        loaded = 0
        errors = 0
        normalized_count = 0
        for url, source, date, score in rows:
            try:
                if not url or not isinstance(url, str):
                    raise ValueError("Invalid URL")
                # v0.4.0: Normalize URL to reduce duplicates
                url_normalized = normalize_url(url)
                if url_normalized != url:
                    normalized_count += 1
                self._urls.add(url_normalized)
                self._url_meta[url_normalized] = EntryMetadata(source, date, score)
                loaded += 1
            except Exception as e:
                logger.warning(f"Skipping invalid URL entry: {e}")
                errors += 1
        if errors > 0:
            logger.info(f"Loaded {loaded} URLs ({normalized_count} normalized, {errors} errors)")
        else:
            logger.debug(f"Loaded {loaded} URLs ({normalized_count} normalized)")
        return normalized_count

    def load_ips(self, rows) -> int:
        """Load all IP and CIDR rows; returns the integer-stored IPv4 count."""
        loaded_ips = 0
        loaded_cidrs = 0
        errors = 0
        ips_as_int = 0
        for ip, source, date, score in rows:
            try:
                if not ip or not isinstance(ip, str):
                    raise ValueError("Invalid IP")
                if '/' in ip:
                    stored = self._cidr.load(ip, EntryMetadata(source, date, score))
                    loaded_cidrs += stored
                    errors += (1 - stored)
                else:
                    # Single IP - v0.4.0: Store IPv4 as integer
                    ips_as_int += self._load_single_ip(ip, EntryMetadata(source, date, score))
                    loaded_ips += 1
            except Exception as e:
                logger.warning(f"Skipping invalid IP entry: {e}")
                errors += 1
        if errors > 0:
            logger.info(
                f"Loaded {loaded_ips} IPs ({ips_as_int} as integers), {loaded_cidrs} CIDRs ({errors} errors)"
            )
        else:
            logger.debug(f"Loaded {loaded_ips} IPs ({ips_as_int} as integers), {loaded_cidrs} CIDRs")
        return ips_as_int

    def _load_single_ip(self, ip: str, metadata: EntryMetadata) -> int:
        """Store one non-CIDR row; returns 1 when it landed in int storage."""
        ip_int = ip_to_int(ip)
        if ip_int is not None:
            # IPv4 - store as integer
            self._ips_int.add(ip_int)
            self._ip_int_meta[ip_int] = metadata
            return 1
        # IPv6 - keep as string
        self._ips_str.add(ip)
        self._ip_meta[ip] = metadata
        return 0

    # ========== Membership checks ==========

    @staticmethod
    def _domain_chain(domain: str) -> List[str]:
        """The domain plus each parent, most-specific first."""
        parts = domain.split('.')
        return ['.'.join(parts[i:]) for i in range(len(parts))]

    def has_domain(self, domain: str) -> bool:
        """Exact or parent-domain membership (``domain`` is pre-lowercased)."""
        return any(sub in self._domains for sub in self._domain_chain(domain))

    def has_url(self, url_normalized: str) -> bool:
        """Exact-match membership on the canonical URL form."""
        return url_normalized in self._urls

    def has_ip(self, ip: str) -> bool:
        """Exact-match or CIDR-membership check for one IP string."""
        ip_int = ip_to_int(ip)
        if ip_int is not None:
            # IPv4 - check as integer
            if ip_int in self._ips_int:
                return True
        else:
            # Not a parseable IPv4 — reject malformed input before it can be
            # treated as an IPv6 string or reach the radix trees, where
            # pytricia raises SystemError on unparseable keys.
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                return False
            # IPv6 - check as string
            if ip in self._ips_str:
                return True
        return self._cidr.has(ip)

    # ========== Source attribution ==========

    def domain_source(self, domain: str) -> Optional[str]:
        """Source for a domain or its nearest blacklisted parent."""
        for sub in self._domain_chain(domain):
            metadata = self._domain_meta.get(sub)
            if metadata:
                return metadata.source
        return None

    def url_source(self, url_normalized: str) -> Optional[str]:
        """Source for a canonical URL form, or None."""
        metadata = self._url_meta.get(url_normalized)
        return metadata.source if metadata else None

    def ip_source(self, ip: str) -> Optional[str]:
        """Source for an exact IP or its containing range, or None."""
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
        return self._cidr.source(ip)
