# Architecture

## Overview

sec-mcp is a Python library, Click CLI and MCP server (stdio transport) that
checks domains, URLs and IP addresses against security blacklists stored in a
local SQLite database. The package is import-clean: `import sec_mcp`,
`sec_mcp.cli` and `sec_mcp.mcp_server` have no side effects — no database is
created, no log file opened, no thread started. Constructing `SecMCP()` is the
side-effect boundary, which is why both entry-point modules build their shared
instance lazily through a `get_core()` singleton (`sec_mcp/cli.py:16`,
`sec_mcp/mcp_server.py:48`) instead of at import time.

## Component map

```
sec-mcp CLI (cli.py)          sec-mcp-server (start_server.py)
        |                                 |
        +-------- get_core() -------------+
                          |
                    SecMCP facade (sec_mcp.py)
                    CheckResult / StatusInfo
                     /              \
        create_storage()      BlacklistUpdater (update_blacklist.py)
        (storage.py)           |  httpx downloads, schedule daily job,
         /          \          |  rate limit, MCP_CACHE_DIR feed cache
   Storage (v1)   HybridStorage (v2)      FeedParser (feed_parsers.py)
   storage_queries  storage_v2_{db,index,writes,stats}
         \          /
        storage_base.py — shared schema, resolve_db_path,
        normalize_url, StorageProtocol
```

- **`SecMCP` facade** (`sec_mcp.py`) — the public API exported from
  `sec_mcp/__init__.py`: `check`, `check_domain`, `check_url`, `check_ip`,
  `check_batch`, `get_status`, `update`, `sample`, `scheduler_alive`, plus the
  `CheckResult` and `StatusInfo` dataclasses. Construction wires
  `create_storage()` to a `BlacklistUpdater`.
- **Entry points** (`pyproject.toml` `[project.scripts]`) — `sec-mcp` →
  `sec_mcp.cli:cli` (Click group: `check`, `check-domain`, `check-url`,
  `check-ip`, `batch`, `status`, `update`, `flush-cache`, `sample` — all but
  `sample` accept `--json`); `sec-mcp-server` → `sec_mcp.start_server:main`,
  which configures logging from `config.json`'s `log_level`, eagerly builds
  the core, then runs `mcp.run(transport="stdio")`.
- **`BlacklistUpdater`** (`update_blacklist.py`) — downloads the ten feeds
  listed in `sec_mcp/config.json` over HTTPS only, enforces the
  `max_feed_bytes` / `min_feed_entries` / `max_feed_entries` /
  `max_range_addresses` sanity bounds, caches feed files under
  `MCP_CACHE_DIR` (platformdirs cache dir by default), and writes each feed
  atomically via `storage.add_entries`. A `schedule` job runs `update_all`
  daily at `update_time`; `force_update()` is rate limited to one run per
  `min_update_interval_seconds` (default 300). `MCP_DISABLE_SCHEDULER=1`
  suppresses the background thread.
- **`FeedParser`** (`feed_parsers.py`) — one parser per feed source (each of
  the ten feeds has its own format), plus dedupe, dispatched by source name.
- **`utility.py`** — `validate_input` (domain/URL/IP incl. IPv6 literals),
  `setup_logging` (`MCP_LOG_PATH` or platformdirs log dir), `load_config`,
  `package_version` (installed metadata first, `pyproject.toml` in a source
  tree).

## Storage layer

`create_storage()` selects the backend on `MCP_USE_V2_STORAGE`: `true` →
`HybridStorage` (v2); anything else → `Storage` (v1). Both satisfy the
structural `StorageProtocol` in `storage_base.py` — the contract test suite
parametrizes both and asserts identical behavior.

**Shared foundation (`storage_base.py`)** — one canonical SQLite schema
(`blacklist_domain` / `blacklist_url` / `blacklist_ip` / `updates` tables with
source indexes), WAL + `synchronous=NORMAL` PRAGMAs, `resolve_db_path`
(explicit arg → `MCP_DB_PATH` → platformdirs default), `normalize_url` (the
single canonicalizer — lowercase, default `http` scheme, tracking-param
stripping, trailing-slash/fragment removal — applied on write, lookup and a
one-shot `PRAGMA user_version` migration so both backends return identical
verdicts), and `init_db`.

**v1 `Storage`** (`storage.py` + `storage_queries.py`) — database-backed with
an LRU positive-hit cache (`cache_size` from `config.json`) and a lazily
loaded, write-invalidated in-memory CIDR range list so IP lookups never scan
the table. `shared_connection()` installs a thread-local ambient connection:
an outer call opens one `sqlite3.connect` and nested calls reuse it, so a
whole `SecMCP.check()` costs at most one connect.

**v2 `HybridStorage`** (`storage_v2.py`) — keeps one O(1) in-memory index per
entry type (`storage_v2_index.EntryIndex`: domain/URL hash sets, IPv4 stored
as integers, IPv6 as strings, CIDR matching via `pytricia` when installed and
a pure-Python `ipaddress` fallback otherwise). All SQLite access is confined
to `storage_v2_db.SQLiteStore`; `storage_v2_writes.DualWriteMixin` keeps memory
and DB in step (with rollback of the in-memory index on persistence failure);
`storage_v2_stats.StorageStatsMixin` serves counts/history. Reload builds the
new index on a scratch instance and swaps it under the lock — readers never
take the lock and always see a complete snapshot. `get_metrics()` reports
lookup counters, hit rate, memory and `using_pytricia`. `shared_connection()`
is a no-op here — lookups are in-memory.

## Check semantics

`SecMCP.check` types the input (`is_ip` → `ipaddress`, `is_url` → `https?://`
prefix, `is_domain` → dotted non-URL non-IP heuristic) and applies the
domain→URL cascade:

- A blacklisted domain makes all URLs from it **or its subdomains** blacklisted
  (parent-domain walk on lookup).
- A blacklisted URL does **not** blacklist its domain.
- IP checks match exact entries or any containing CIDR network.

All checks run inside `shared_connection()` and return
`CheckResult(blacklisted, explanation)` — `to_dict()` maps to
`{"is_safe": ..., "explain": ...}`.

## MCP layer

`mcp_server.py` builds an SDK-2.x `MCPServer` (identity fields feed
`serverInfo` and `instructions`) with six tools: `check_batch`, `get_status`,
`update_blacklists`, `get_diagnostics` (modes `summary` / `full` / `health` /
`performance` / `sample`), `add_entry`, `remove_entry`.

- Each tool declares a pydantic return model, so `tools/list` exposes an
  `outputSchema` and results carry `structuredContent` beside the text
  `content` (older clients keep working).
- `check_batch` items carry a tri-state `verdict`: `safe` / `blacklisted` /
  `invalid` (via `validate_input`).
- Domain failures return `CallToolResult(isError=True)` — only `MCPError`
  re-raises as a JSON-RPC protocol error.
- `update_blacklists` offloads the blocking update to `anyio.to_thread` and
  bridges `notifications/progress` back onto the loop with
  `anyio.from_thread.run` — one notification per source when the caller sent
  a progress token.

## Configuration and data locations

- `sec_mcp/config.json` (shipped package data): `blacklist_sources` (10
  feeds), `update_time`, `min_update_interval_seconds`, `cache_size`,
  `max_feed_bytes`, `min_feed_entries`, `max_feed_entries`,
  `max_range_addresses`, `log_level`.
- Environment: `MCP_DB_PATH`, `MCP_USE_V2_STORAGE`, `MCP_LOG_PATH`,
  `MCP_CACHE_DIR`, `MCP_DISABLE_SCHEDULER` — full reference in
  [agent-env.md](agent-env.md).
- Defaults via platformdirs: macOS `~/Library/Application Support/sec-mcp/`,
  Linux `~/.local/share/sec-mcp/`, Windows `%APPDATA%\sec-mcp\`.

## See also

- [decisions/](decisions/) — ADRs (pytricia opt-in packaging, coverage M3
  target)
- [agent-env.md](agent-env.md) — toolchain, env vars, probe isolation
- [playbook.md](playbook.md) — usage cookbook
- [../BENCHMARK_PLAYBOOK.md](../BENCHMARK_PLAYBOOK.md) — benchmark methodology
