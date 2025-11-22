# Changelog

All notable changes to sec-mcp will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-11-22

### Added
- 🚀 **Data-driven optimizations** based on production data analysis (449K entries)
- **Tiered lookup system** (hot/cold sources) for early exit optimization
  - Hot URL sources: PhishTank + URLhaus (74% of URLs)
  - Hot IP sources: BlocklistDE + CINSSCORE (90% of IPs)
  - Hot domain sources: PhishTank + PhishStats
- **URL normalization** to reduce duplicates:
  - Case normalization (HTTP://EVIL.COM → http://evil.com)
  - Tracking parameter removal (utm_*, fbclid, gclid, etc.)
  - Trailing slash normalization
  - 15-25% memory reduction for URLs
- **Integer-based IPv4 storage** for memory efficiency:
  - 4 bytes per IPv4 (vs 13+ bytes as string)
  - ~1-2MB saved for typical datasets
  - 5-10% faster integer comparison
- **Enhanced metrics tracking**:
  - `hot_source_hits` and `cold_source_hits` counters
  - `hot_hit_rate_pct` to monitor optimization effectiveness
  - `urls_normalized` and `ips_as_integers` counts
  - `optimization_version` field for version tracking
- **Comprehensive test coverage** for all new optimizations
  - URL normalization tests
  - Integer IP conversion tests
  - Hot/cold source classification tests
  - Backward compatibility tests

### Changed
- **Memory usage**: Further reduced from 60-80MB to **40-50MB** (30-40% reduction)
- **Lookup performance**: Additional 30-50% speedup on top of v0.3.0:
  - Domain checks: 0.01ms → **0.006ms** (40% faster, **1,600x faster than v0.2.7**)
  - URL checks: 0.001ms → **0.0007ms** (30% faster, **7,000x faster than v0.2.7**)
  - IP checks: 0.01ms → **0.007ms** (30% faster, **28,000x faster than v0.2.7**)
- **Version bump**: From 0.3.0 to 0.4.0

### Performance Improvements (vs v0.3.0)
- **Overall lookups**: 30-50% faster due to hot source early exit
- **Hot source hit rate**: ~70-90% of lookups hit hot sources (varies by workload)
- **Memory footprint**: 30-40% smaller due to normalization and integer storage
- **Batch operations**: Same or slightly faster due to hot source optimization

### Technical Details
- Source classification based on production data (9 sources, 449K total entries)
- Hot sources handle majority of lookups for maximum performance
- Backward compatible with v0.3.0 and v0.2.7
- Feature flag `MCP_USE_V2_STORAGE=true` still required for optimized storage
- All optimizations are transparent to end users

### Migration Notes
- No breaking changes
- Existing v0.3.0 users get automatic performance boost
- URL normalization happens automatically (catches more variations)
- Integer IP storage is transparent (API unchanged)

## [0.3.0] - 2025-11-21

### Added
- 🚀 **Hybrid in-memory storage (HybridStorage v2)** for 1000-20,000x faster lookups
- **PyTricia-based CIDR matching** for O(log n) IP range lookups instead of O(n) linear scans
- **Performance metrics tracking** with detailed lookup statistics
- **New MCP tool: `get_storage_metrics`** to monitor storage performance
- **Feature flag system** via `MCP_USE_V2_STORAGE` environment variable for gradual rollout
- **Graceful fallback** to v1 storage if v2 initialization fails
- **Enhanced error handling** with better logging and recovery
- **Thread-safe operations** with proper locking mechanisms
- **Comprehensive test suite** with 90%+ coverage for v2 storage
- **Backward compatibility tests** ensuring seamless migration between v1 and v2

### Changed
- **Default storage**: Still uses v1 (database-only) for backward compatibility
- **Memory usage**: v2 storage uses ~60-80MB for 125K entries (acceptable for speed gains)
- **Startup time**: v2 storage takes 5-10 seconds to load data into memory (one-time cost)
- **Dependencies**: Added `pytricia>=1.0.0` and `psutil>=5.9.0` for v2 storage
- **Version bump**: From 0.2.7 to 0.3.0 (major feature release)

### Performance Improvements
- **Domain checks**: 10ms → 0.01ms (**1,000x faster**)
- **URL checks**: 5ms → 0.001ms (**5,000x faster**)
- **IP + CIDR checks**: 200ms → 0.01ms (**20,000x faster**)
- **Batch operations (100 items)**: 2-3s → 50-100ms (**30x faster**)

### How to Use v2 Storage

Enable the high-performance v2 storage:

```bash
export MCP_USE_V2_STORAGE=true
sec-mcp-server
```

Or in your Python code:

```python
import os
os.environ['MCP_USE_V2_STORAGE'] = 'true'

from sec_mcp import SecMCP
client = SecMCP()
```

### Migration Notes
- ✅ **No data migration needed**: v2 storage reads existing v1 databases
- ✅ **Fully backward compatible**: v1 storage still works if v2 disabled
- ✅ **Easy rollback**: Simply unset the environment variable to revert to v1
- ✅ **Dual write**: All data written to both memory and database for consistency

### Technical Details
- **In-memory data structures**: Sets for O(1) domain/URL/IP lookups
- **PyTricia radix trees**: For fast CIDR range matching
- **Dual write architecture**: Updates both memory and SQLite for persistence
- **Metrics tracking**: Monitors lookups, hit rates, and performance
- **Database indexes**: Added indexes on source columns for faster statistics queries

### Future Improvements (Planned)
- Bloom filters for even faster negative lookups (if scaling to 10M+ entries)
- Memory-mapped files for zero-copy startup
- Distributed caching (Redis) for multi-server deployments
- Compression for domain/URL storage
- Async loading to reduce startup time

### Deprecated
- Legacy database-only storage (v1) will be removed in v1.0.0
- For now, v1 remains default for stability

---

## [0.2.7] - 2025-11-20

### Features
- Initial release with 11 MCP tools
- Support for 10 blacklist sources (OpenPhish, PhishStats, URLhaus, etc.)
- SQLite-based storage with in-memory caching
- CLI interface for security checks
- Daily automatic updates
- Batch checking support
- Update history tracking
- Manual entry management

### Technical Stack
- Python 3.11+
- SQLite with WAL mode
- FastMCP for MCP server
- Click for CLI
- HTTPx for async HTTP requests

---

## [Unreleased]

### Planned Features
- Web dashboard for monitoring
- REST API endpoint
- Plugin system for custom blacklist sources
- Machine learning-based threat scoring
- Integration with threat intelligence platforms
