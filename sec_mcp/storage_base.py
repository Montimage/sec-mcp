"""Shared storage foundation for sec-mcp.

Both storage backends — the legacy :class:`sec_mcp.storage.Storage` and the
hybrid :class:`sec_mcp.storage_v2.HybridStorage` — build on this module so the
SQLite schema (DDL), the default database-path resolution, and the public
storage contract each live in exactly one place.
"""

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple, runtime_checkable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

DB_ENV_VAR = "MCP_DB_PATH"
DEFAULT_DB_FILENAME = "mcp.db"

# PRAGMAs applied to every database connection at initialization time.
DB_PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA cache_size=10000;",
)

# The one canonical schema for both backends. Only secondary indexes are
# declared: an index on a PRIMARY KEY column would duplicate the implicit
# index SQLite already maintains for the key, so none is created. The
# source indexes are cheap on small installs and keep v1/v2 databases
# byte-compatible.
SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS blacklist_domain (
        domain TEXT PRIMARY KEY,
        date TEXT,
        score REAL,
        source TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_domain_source ON blacklist_domain(source);",
    """
    CREATE TABLE IF NOT EXISTS blacklist_url (
        url TEXT PRIMARY KEY,
        date TEXT,
        score REAL,
        source TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_url_source ON blacklist_url(source);",
    """
    CREATE TABLE IF NOT EXISTS blacklist_ip (
        ip TEXT PRIMARY KEY,
        date TEXT,
        score REAL,
        source TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ip_source ON blacklist_ip(source);",
    """
    CREATE TABLE IF NOT EXISTS updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source TEXT NOT NULL,
        entry_count INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_updates_source ON updates(source);",
    "CREATE INDEX IF NOT EXISTS idx_updates_timestamp ON updates(timestamp);",
)

# Indexes pre-deduplication schemas created on columns that are already the
# table's PRIMARY KEY — pure write overhead the planner never uses. New
# databases never get them; init_db drops them idempotently from databases
# created by older versions.
LEGACY_PK_DUPLICATE_INDEXES = (
    "DROP INDEX IF EXISTS idx_blacklist_domain;",
    "DROP INDEX IF EXISTS idx_blacklist_url;",
    "DROP INDEX IF EXISTS idx_blacklist_ip;",
)


def get_default_db_path() -> str:
    """Return the platform-specific default database path.

    Prefers ``platformdirs.user_data_dir`` and falls back to per-OS
    conventions when it is unavailable. The directory is created if needed.
    """
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
    return os.path.join(db_dir, DEFAULT_DB_FILENAME)


def resolve_db_path(db_path: Optional[str] = None) -> str:
    """Resolve the database path.

    Resolution order: the explicit argument, then the ``MCP_DB_PATH``
    environment variable, then the platform default.
    """
    if db_path is None:
        db_path = os.environ.get(DB_ENV_VAR)
    if db_path is None:
        db_path = get_default_db_path()
    return db_path


# Query parameters stripped by normalize_url so variants of the same page
# that differ only in tracking share one blacklist key.
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'mc_eid', '_ga', 'ref', 'referrer'
}


def _canonical_parse(lowered: str):
    """Parse a lowercased URL, reparsing bare hosts under the default scheme."""
    parsed = urlparse(lowered)
    # A bare host (optionally with path/query) has no scheme — urlparse
    # leaves netloc empty and puts everything in path. Reparse with the
    # default scheme so the host lands in netloc instead of producing
    # "http:///host" garbage.
    if not parsed.netloc:
        parsed = urlparse('http://' + lowered.lstrip('/'))
    return parsed


def _canonical_query_string(query: str) -> str:
    """Build the canonical query string with tracking parameters removed."""
    if not query:
        return ''
    query_params = parse_qs(query)
    filtered_params = {
        k: v for k, v in query_params.items()
        if k.lower() not in TRACKING_PARAMS
    }
    return urlencode(filtered_params, doseq=True)


def normalize_url(url: str) -> str:
    """Canonicalize a URL so variants of the same page share one blacklist key.

    This is the single normalization every backend applies — on write, on
    lookup and on the rows already in ``blacklist_url`` — so v1's exact-match
    SQLite lookups and v2's in-memory index return the same verdict.

    Normalization:
    - Convert to lowercase
    - Ensure scheme (default to http if missing, incl. bare hosts)
    - Remove tracking parameters (utm_*, fbclid, etc.)
    - Strip trailing slashes from path (a bare ``/`` path becomes empty)
    - Drop the fragment

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
        lowered = url.lower()
        parsed = _canonical_parse(lowered)
        query_string = _canonical_query_string(parsed.query)

        # Rebuild URL; an all-slash path ("", "/") collapses to "" so
        # "http://host" and "http://host/" share one canonical form.
        normalized = urlunparse((
            parsed.scheme or 'http',  # Default scheme
            parsed.netloc,
            parsed.path.rstrip('/'),  # Remove trailing slash(es)
            '',  # params (deprecated)
            query_string,
            ''  # fragment (ignore)
        ))

        return normalized
    except ValueError:
        # urlparse rejects some malformed hosts (e.g. bad IPv6 brackets) —
        # return the original lowercase so the lookup simply misses.
        return url.lower()


def _canonicalize_url_rows(conn: sqlite3.Connection) -> None:
    """Rewrite ``blacklist_url`` rows to their canonical ``normalize_url`` form.

    Rows written before normalization existed — or inserted directly — keep
    whatever raw variant was stored, which v1's exact-match lookups cannot
    find under a different variant. Canonicalizing once at init makes the
    table itself normalized, so both backends agree on every variant.
    ``INSERT OR REPLACE`` merges rows whose variants collapse onto one
    canonical URL.
    """
    rows = conn.execute(
        "SELECT url, date, score, source FROM blacklist_url"
    ).fetchall()
    for url, date, score, source in rows:
        normalized = normalize_url(url)
        if normalized != url:
            conn.execute("DELETE FROM blacklist_url WHERE url = ?", (url,))
            conn.execute(
                "INSERT OR REPLACE INTO blacklist_url (url, date, score, source) VALUES (?, ?, ?, ?)",
                (normalized, date, score, source),
            )


# ``PRAGMA user_version`` marks one-shot migrations already applied so
# re-opening a database skips them. Version 1 = ``blacklist_url`` rows
# canonicalized to ``normalize_url`` form.
SCHEMA_VERSION = 1


def init_db(db_path: str) -> None:
    """Apply the shared PRAGMAs, create the schema and run pending one-shot
    migrations in the database at ``db_path``."""
    with sqlite3.connect(db_path) as conn:
        for pragma in DB_PRAGMAS:
            conn.execute(pragma)
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        for statement in LEGACY_PK_DUPLICATE_INDEXES:
            conn.execute(statement)
        # _canonicalize_url_rows rewrites every stored URL — too expensive
        # to re-run on every open, so it runs once and stamps user_version.
        if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
            _canonicalize_url_rows(conn)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()


@runtime_checkable
class StorageProtocol(Protocol):
    """The contract every blacklist storage backend satisfies.

    Structural typing only — the contract suite parametrizes both backends and
    asserts ``isinstance(storage, StorageProtocol)`` plus identical behavior for
    every operation declared here.
    """

    db_path: str

    # ----- Lookups -----
    def is_domain_blacklisted(self, domain: str) -> bool: ...

    def is_url_blacklisted(self, url: str) -> bool: ...

    def is_ip_blacklisted(self, ip: str) -> bool: ...

    # ----- Source attribution -----
    def get_domain_blacklist_source(self, domain: str) -> Optional[str]: ...

    def get_url_blacklist_source(self, url: str) -> Optional[str]: ...

    def get_ip_blacklist_source(self, ip: str) -> Optional[str]: ...

    # ----- Writes -----
    def add_domain(self, domain: str, date: str, score: float, source: str) -> None: ...

    def add_url(self, url: str, date: str, score: float, source: str) -> None: ...

    def add_ip(self, ip: str, date: str, score: float, source: str) -> None: ...

    def add_domains(self, domains: List[Tuple[str, str, float, str]]) -> None: ...

    def add_urls(self, urls: List[Tuple[str, str, float, str]]) -> None: ...

    def add_ips(self, ips: List[Tuple[str, str, float, str]]) -> None: ...

    def add_entries(self, entries: List[Tuple[Optional[str], Optional[str], str, float, str]]) -> None: ...

    def remove_entry(self, value: str) -> bool: ...

    # ----- Statistics & history -----
    def count_entries(self) -> int: ...

    def get_source_counts(self) -> Dict[str, int]: ...

    def get_source_type_counts(self) -> Dict[str, dict]: ...

    def get_active_sources(self) -> List[str]: ...

    def sample_entries(self, count: int = 10) -> List[str]: ...

    def get_last_update(self) -> datetime: ...

    def get_last_update_per_source(self) -> Dict[str, str]: ...

    def get_update_history(
        self, source: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None
    ) -> list: ...

    def log_update(self, source: str, entry_count: int) -> None: ...

    def flush_cache(self) -> bool: ...

    # ----- Connection scope -----
    def shared_connection(self):
        """Context manager: run a sequence of storage calls on one connection.

        The v1 backend routes every call made on this thread inside the
        block through a single ambient ``sqlite3.Connection``; the v2
        backend is a no-op (its lookups are in-memory). ``SecMCP.check``
        enters it so a whole check costs at most one ``sqlite3.connect``.
        """
        ...
