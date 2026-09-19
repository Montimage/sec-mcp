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

DB_ENV_VAR = "MCP_DB_PATH"
DEFAULT_DB_FILENAME = "mcp.db"

# PRAGMAs applied to every database connection at initialization time.
DB_PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA cache_size=10000;",
)

# The one canonical schema for both backends. The source indexes are cheap on
# small installs and keep v1/v2 databases byte-compatible.
SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS blacklist_domain (
        domain TEXT PRIMARY KEY,
        date TEXT,
        score REAL,
        source TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_blacklist_domain ON blacklist_domain(domain);",
    "CREATE INDEX IF NOT EXISTS idx_domain_source ON blacklist_domain(source);",
    """
    CREATE TABLE IF NOT EXISTS blacklist_url (
        url TEXT PRIMARY KEY,
        date TEXT,
        score REAL,
        source TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_blacklist_url ON blacklist_url(url);",
    "CREATE INDEX IF NOT EXISTS idx_url_source ON blacklist_url(source);",
    """
    CREATE TABLE IF NOT EXISTS blacklist_ip (
        ip TEXT PRIMARY KEY,
        date TEXT,
        score REAL,
        source TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_blacklist_ip ON blacklist_ip(ip);",
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


def init_db(db_path: str) -> None:
    """Apply the shared PRAGMAs and create the schema in the database at ``db_path``."""
    with sqlite3.connect(db_path) as conn:
        for pragma in DB_PRAGMAS:
            conn.execute(pragma)
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
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
