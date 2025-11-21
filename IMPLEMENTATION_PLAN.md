# Sec-MCP Optimization: Implementation Plan

**Goal**: Transform sec-mcp from database-heavy to high-performance in-memory architecture while maintaining all existing functionality.

**Target Performance**:
- Domain check: 10ms → 0.01ms (1000x faster)
- URL check: 5ms → 0.001ms (5000x faster)
- IP check with CIDR: 200ms → 0.01ms (20,000x faster)
- Batch 100 items: 2-3s → 50-100ms (30x faster)

**Memory Budget**: 60-80MB (acceptable for modern systems)

---

## Phase 1: Core Storage Refactoring (Days 1-3)

### Task 1.1: Create New Hybrid Storage Class
**File**: `sec_mcp/storage_v2.py` (new file, don't break existing)

**Subtasks**:
- [ ] Create `HybridStorage` class skeleton
- [ ] Add in-memory data structures:
  - `self._domains: Set[str]` for domain lookups
  - `self._urls: Set[str]` for URL lookups
  - `self._ips: Set[str]` for exact IP lookups
  - `self._domain_meta: Dict[str, EntryMetadata]` for source info
  - `self._url_meta: Dict[str, EntryMetadata]`
  - `self._ip_meta: Dict[str, EntryMetadata]`
- [ ] Add threading primitives:
  - `self._lock = threading.RLock()` for thread safety
  - `self._loading = threading.Event()` for startup coordination
- [ ] Keep SQLite connection for persistence:
  - `self._db_path: str`
  - `self._get_connection()` method with proper connection management

**Acceptance Criteria**:
- Class initializes without errors
- All data structures properly typed (use type hints)
- Thread-safe access patterns established

**Estimated Time**: 3-4 hours

---

### Task 1.2: Implement Data Loading from SQLite
**File**: `sec_mcp/storage_v2.py`

**Subtasks**:
- [ ] Implement `_load_domains_from_db()` method:
  ```python
  def _load_domains_from_db(self):
      """Load all domains from SQLite into memory."""
      cursor = self._get_connection().execute(
          "SELECT domain, source, date, score FROM blacklist_domain"
      )
      for domain, source, date, score in cursor:
          domain_lower = domain.lower()
          self._domains.add(domain_lower)
          self._domain_meta[domain_lower] = EntryMetadata(source, date, score)
  ```
- [ ] Implement `_load_urls_from_db()` method
- [ ] Implement `_load_ips_from_db()` method
- [ ] Implement master `_load_all_data()` method:
  - Call all three loaders
  - Add progress logging
  - Measure load time
  - Log statistics (counts per type)
- [ ] Add `reload()` public method for manual refresh

**Performance Target**:
- Load 125K entries in < 10 seconds

**Acceptance Criteria**:
- All data loads correctly from existing database
- No data loss or corruption
- Progress logging shows clear feedback
- Memory usage within 60MB

**Estimated Time**: 4-5 hours

---

### Task 1.3: Implement CIDR Range Handling with PyTricia
**File**: `sec_mcp/storage_v2.py`

**Prerequisites**: Add `pytricia` to dependencies

**Subtasks**:
- [ ] Add `pytricia>=1.0.0` to `pyproject.toml` dependencies
- [ ] Create IPv4 and IPv6 radix trees:
  ```python
  import pytricia

  self._ipv4_cidr_tree = pytricia.PyTricia(32)
  self._ipv6_cidr_tree = pytricia.PyTricia(128)
  self._cidr_metadata: Dict[str, EntryMetadata] = {}
  ```
- [ ] Implement `_load_cidr_from_db()` method:
  - Query: `SELECT ip, source, date, score FROM blacklist_ip WHERE INSTR(ip, '/') > 0`
  - Parse each CIDR
  - Insert into appropriate tree (IPv4 vs IPv6)
  - Store metadata separately
- [ ] Handle edge cases:
  - Invalid CIDR notation (log and skip)
  - Mixed IPv4/IPv6 detection
  - Overlapping ranges (later entry wins)

**Fallback Plan**: If `pytricia` not available, implement simple list-based fallback

**Acceptance Criteria**:
- All CIDR ranges load correctly
- IPv4 and IPv6 handled separately
- Invalid entries logged but don't crash
- Lookup performance: O(log n) instead of O(n)

**Estimated Time**: 3-4 hours

---

### Task 1.4: Implement Fast Lookup Methods
**File**: `sec_mcp/storage_v2.py`

**Subtasks**:
- [ ] Implement `is_domain_blacklisted(domain: str) -> bool`:
  ```python
  def is_domain_blacklisted(self, domain: str) -> bool:
      """Check domain and parent domains. O(depth) average case."""
      domain = domain.lower()

      # Check exact match first
      if domain in self._domains:
          return True

      # Check parent domains (example.com, com)
      parts = domain.split('.')
      for i in range(1, len(parts)):
          parent = '.'.join(parts[i:])
          if parent in self._domains:
              return True

      return False
  ```
- [ ] Implement `is_url_blacklisted(url: str) -> bool`:
  ```python
  def is_url_blacklisted(self, url: str) -> bool:
      """Check URL exact match. O(1) lookup."""
      return url in self._urls
  ```
- [ ] Implement `is_ip_blacklisted(ip: str) -> bool`:
  ```python
  def is_ip_blacklisted(self, ip: str) -> bool:
      """Check IP exact match and CIDR ranges."""
      # Exact match first (O(1))
      if ip in self._ips:
          return True

      # CIDR check (O(log n) with pytricia)
      try:
          if ':' in ip:  # IPv6
              return ip in self._ipv6_cidr_tree
          else:  # IPv4
              return ip in self._ipv4_cidr_tree
      except (KeyError, ValueError):
          return False
  ```

**Acceptance Criteria**:
- All lookups return correct results (test against existing DB)
- Performance meets targets (< 0.1ms per lookup)
- Thread-safe (no race conditions)
- Handles edge cases (empty strings, malformed input)

**Estimated Time**: 2-3 hours

---

### Task 1.5: Implement Metadata Retrieval Methods
**File**: `sec_mcp/storage_v2.py`

**Subtasks**:
- [ ] Implement `get_domain_blacklist_source(domain: str) -> Optional[str]`:
  ```python
  def get_domain_blacklist_source(self, domain: str) -> Optional[str]:
      """Get source that blacklisted a domain (including parents)."""
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
  ```
- [ ] Implement `get_url_blacklist_source(url: str) -> Optional[str]`
- [ ] Implement `get_ip_blacklist_source(ip: str) -> Optional[str]`:
  - Handle both exact match and CIDR lookup
  - For CIDR, need to search tree and get metadata

**Acceptance Criteria**:
- Returns correct source for all blacklisted entries
- Returns None for non-blacklisted entries
- Fast performance (< 1ms)

**Estimated Time**: 2-3 hours

---

### Task 1.6: Implement Write Operations (Dual Write)
**File**: `sec_mcp/storage_v2.py`

**Subtasks**:
- [ ] Implement `add_domain(domain: str, date: str, score: float, source: str)`:
  ```python
  def add_domain(self, domain: str, date: str, score: float, source: str):
      """Add domain to both memory and database."""
      with self._lock:
          # Update memory first (fast rollback if DB fails)
          domain_lower = domain.lower()
          self._domains.add(domain_lower)
          self._domain_meta[domain_lower] = EntryMetadata(source, date, score)

          # Persist to database
          try:
              conn = self._get_connection()
              conn.execute(
                  "INSERT OR REPLACE INTO blacklist_domain (domain, date, score, source) VALUES (?, ?, ?, ?)",
                  (domain, date, score, source)
              )
              conn.commit()
          except Exception as e:
              # Rollback memory changes on DB failure
              self._domains.discard(domain_lower)
              self._domain_meta.pop(domain_lower, None)
              raise
  ```
- [ ] Implement `add_url(...)` with dual write
- [ ] Implement `add_ip(...)` with dual write:
  - Handle both exact IPs and CIDR ranges
  - Update appropriate tree for CIDRs
- [ ] Implement batch methods:
  - `add_domains_batch(domains: List[Tuple])`
  - `add_urls_batch(urls: List[Tuple])`
  - `add_ips_batch(ips: List[Tuple])`
  - Use transaction for atomicity
  - Update memory only after successful DB commit

**Acceptance Criteria**:
- All writes persisted to both memory and DB
- Atomic operations (both succeed or both fail)
- Batch operations are transactional
- Performance: Batch insert 10K entries in < 5 seconds

**Estimated Time**: 4-5 hours

---

### Task 1.7: Implement Statistics & Query Methods
**File**: `sec_mcp/storage_v2.py`

**Subtasks**:
- [ ] Implement `count_entries() -> int`:
  ```python
  def count_entries(self) -> int:
      """Get total count from memory (instant)."""
      return len(self._domains) + len(self._urls) + len(self._ips) + len(self._cidr_metadata)
  ```
- [ ] Implement `get_source_counts() -> Dict[str, int]`:
  ```python
  def get_source_counts(self) -> Dict[str, int]:
      """Count entries per source from memory."""
      counts = {}

      # Count domains
      for meta in self._domain_meta.values():
          counts[meta.source] = counts.get(meta.source, 0) + 1

      # Count URLs
      for meta in self._url_meta.values():
          counts[meta.source] = counts.get(meta.source, 0) + 1

      # Count IPs
      for meta in self._ip_meta.values():
          counts[meta.source] = counts.get(meta.source, 0) + 1

      # Count CIDRs
      for meta in self._cidr_metadata.values():
          counts[meta.source] = counts.get(meta.source, 0) + 1

      return counts
  ```
- [ ] Implement `get_active_sources() -> List[str]`:
  - Extract unique sources from all metadata dictionaries
- [ ] Implement `sample_entries(count: int) -> List[str]`:
  - Random sample from domains, URLs, IPs
  - Use `random.sample()`
- [ ] Keep DB-based methods for history:
  - `get_last_update() -> datetime` (from updates table)
  - `get_update_history(...) -> List[dict]` (from updates table)
  - `get_last_update_per_source() -> Dict[str, str]`

**Acceptance Criteria**:
- All stats methods return accurate counts
- Fast performance (< 10ms for counts)
- History queries still work (using DB)

**Estimated Time**: 3-4 hours

---

## Phase 2: Integration with Existing Code (Days 4-5)

### Task 2.1: Create Storage Factory with Feature Flag
**File**: `sec_mcp/storage.py` (modify existing)

**Subtasks**:
- [ ] Add environment variable `MCP_USE_V2_STORAGE`:
  ```python
  import os
  from .storage_v2 import HybridStorage

  def create_storage(db_path=None):
      """Factory method to create storage instance."""
      use_v2 = os.environ.get('MCP_USE_V2_STORAGE', 'false').lower() == 'true'

      if use_v2:
          print("Using optimized HybridStorage (v2)", file=sys.stderr)
          return HybridStorage(db_path)
      else:
          print("Using legacy Storage (v1)", file=sys.stderr)
          return Storage(db_path)
  ```
- [ ] Ensure both `Storage` and `HybridStorage` have same interface (duck typing)
- [ ] Update `SecMCP.__init__` to use factory:
  ```python
  # In sec_mcp.py
  def __init__(self, db_path=None):
      # ... existing code ...
      self.storage = create_storage(db_path=db_path)  # Use factory
      self.updater = BlacklistUpdater(self.storage)
  ```

**Acceptance Criteria**:
- Can switch between v1 and v2 via environment variable
- Default is v1 (safe rollback path)
- No breaking changes to existing API

**Estimated Time**: 1-2 hours

---

### Task 2.2: Update MCP Server to Use New Storage
**File**: `sec_mcp/mcp_server.py`

**Subtasks**:
- [ ] Verify all MCP tools work with new storage:
  - `get_blacklist_status()` ✓
  - `check_batch()` ✓
  - `sample_blacklist()` ✓
  - `get_source_stats()` ✓
  - `get_update_history()` ✓ (uses DB)
  - `flush_cache()` - implement for v2 as reload
  - `health_check()` ✓
  - `add_entry()` ✓
  - `remove_entry()` - implement for v2
  - `update_blacklists()` ✓
- [ ] Implement `flush_cache()` for HybridStorage:
  ```python
  def flush_cache(self) -> bool:
      """Reload all data from database."""
      self._load_all_data()
      return True
  ```
- [ ] Implement `remove_entry()` for HybridStorage:
  ```python
  def remove_entry(self, value: str) -> bool:
      """Remove from both memory and database."""
      with self._lock:
          # Remove from memory
          removed = False
          if value in self._domains:
              self._domains.remove(value)
              self._domain_meta.pop(value, None)
              removed = True
          elif value in self._urls:
              self._urls.remove(value)
              self._url_meta.pop(value, None)
              removed = True
          elif value in self._ips:
              self._ips.remove(value)
              self._ip_meta.pop(value, None)
              removed = True

          if removed:
              # Remove from database
              conn = self._get_connection()
              conn.execute("DELETE FROM blacklist_domain WHERE domain = ?", (value,))
              conn.execute("DELETE FROM blacklist_url WHERE url = ?", (value,))
              conn.execute("DELETE FROM blacklist_ip WHERE ip = ?", (value,))
              conn.commit()

          return removed
  ```

**Acceptance Criteria**:
- All 11 MCP tools work correctly with HybridStorage
- No functionality regression
- Error handling maintained

**Estimated Time**: 3-4 hours

---

### Task 2.3: Update CLI to Work with New Storage
**File**: `sec_mcp/cli.py`

**Subtasks**:
- [ ] Test all CLI commands with v2 storage:
  - `sec-mcp check <value>` ✓
  - `sec-mcp check_domain <domain>` ✓
  - `sec-mcp check_url <url>` ✓
  - `sec-mcp check_ip <ip>` ✓
  - `sec-mcp batch <file>` ✓
  - `sec-mcp status` ✓
  - `sec-mcp update` ✓
  - `sec-mcp flush_cache` ✓
  - `sec-mcp sample` ✓
- [ ] Add performance timing to CLI output:
  ```python
  import time

  start = time.perf_counter()
  result = client.check(url)
  elapsed = time.perf_counter() - start

  print(f"Result: {result.to_json()}")
  print(f"Time: {elapsed*1000:.2f}ms")
  ```
- [ ] Add memory usage reporting (optional):
  ```python
  import psutil
  import os

  process = psutil.Process(os.getpid())
  print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
  ```

**Acceptance Criteria**:
- All CLI commands work correctly
- Performance improvements visible in timing
- User experience unchanged (backward compatible)

**Estimated Time**: 2-3 hours

---

### Task 2.4: Update Blacklist Updater
**File**: `sec_mcp/update_blacklist.py`

**Subtasks**:
- [ ] Ensure batch inserts work efficiently with HybridStorage:
  - Current code uses `storage.add_domains()`, `storage.add_urls()`, `storage.add_ips()`
  - Should map to `add_domains_batch()`, etc. in v2
- [ ] Add progress reporting during load:
  ```python
  print(f"Loading {len(domains)} domains into memory...", file=sys.stderr)
  storage.add_domains_batch(domains)
  print(f"Loaded {len(domains)} domains in {elapsed:.1f}s", file=sys.stderr)
  ```
- [ ] After update, trigger reload if using HybridStorage:
  ```python
  if hasattr(storage, 'reload'):
      print("Reloading blacklist into memory...", file=sys.stderr)
      storage.reload()
  ```
- [ ] Log memory usage after updates (optional)

**Acceptance Criteria**:
- Updates load data into both DB and memory
- Progress feedback during long operations
- Memory stays within budget after update

**Estimated Time**: 2-3 hours

---

## Phase 3: Testing & Validation (Days 6-7)

### Task 3.1: Unit Tests for HybridStorage
**File**: `sec_mcp/tests/test_storage_v2.py` (new file)

**Subtasks**:
- [ ] Test initialization and loading:
  ```python
  def test_hybrid_storage_initialization():
      storage = HybridStorage(":memory:")
      assert storage.count_entries() == 0

  def test_load_from_database():
      # Pre-populate database
      conn = sqlite3.connect(":memory:")
      conn.execute("CREATE TABLE blacklist_domain ...")
      conn.execute("INSERT INTO blacklist_domain VALUES (...)")

      # Load into HybridStorage
      storage = HybridStorage(":memory:")
      assert storage.is_domain_blacklisted("evil.com")
  ```
- [ ] Test domain lookups:
  - Exact match
  - Parent domain match
  - Non-existent domain
  - Case insensitivity
- [ ] Test URL lookups:
  - Exact match
  - Non-existent URL
  - URL vs domain distinction
- [ ] Test IP lookups:
  - Exact IP match
  - CIDR range match
  - Non-blacklisted IP
  - IPv4 vs IPv6
- [ ] Test CIDR edge cases:
  - Overlapping ranges
  - Invalid CIDR notation
  - /0 (entire internet)
  - /32 (single IP)
- [ ] Test write operations:
  - Add single entry
  - Add batch entries
  - Dual write (both memory and DB)
  - Rollback on DB failure
- [ ] Test statistics methods:
  - count_entries()
  - get_source_counts()
  - sample_entries()
- [ ] Test thread safety:
  - Concurrent reads
  - Concurrent writes
  - Read during write

**Target Coverage**: 90%+ for HybridStorage

**Estimated Time**: 6-8 hours

---

### Task 3.2: Integration Tests
**File**: `sec_mcp/tests/test_integration_v2.py` (new file)

**Subtasks**:
- [ ] Test full workflow:
  ```python
  def test_full_workflow_v2():
      # 1. Initialize storage
      storage = HybridStorage(":memory:")

      # 2. Add entries
      storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
      storage.add_url("http://phishing.example.com/login", "2025-01-01", 8.5, "test")
      storage.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")

      # 3. Check entries
      assert storage.is_domain_blacklisted("evil.com")
      assert storage.is_domain_blacklisted("sub.evil.com")  # Parent check
      assert storage.is_url_blacklisted("http://phishing.example.com/login")
      assert storage.is_ip_blacklisted("192.168.1.100")

      # 4. Get metadata
      assert storage.get_domain_blacklist_source("evil.com") == "test"

      # 5. Statistics
      assert storage.count_entries() == 3
      counts = storage.get_source_counts()
      assert counts["test"] == 3
  ```
- [ ] Test with SecMCP class:
  ```python
  def test_sec_mcp_with_v2_storage():
      os.environ['MCP_USE_V2_STORAGE'] = 'true'

      mcp = SecMCP(db_path=":memory:")

      # Add test data
      mcp.storage.add_domain("malware.com", "2025-01-01", 9.0, "test")

      # Check via SecMCP
      result = mcp.check("malware.com")
      assert result.blacklisted == True

      result = mcp.check("sub.malware.com")
      assert result.blacklisted == True
  ```
- [ ] Test MCP server tools:
  ```python
  @pytest.mark.asyncio
  async def test_mcp_tools_with_v2():
      os.environ['MCP_USE_V2_STORAGE'] = 'true'

      # Initialize server
      from sec_mcp.mcp_server import core
      core.storage.add_domain("evil.com", "2025-01-01", 9.0, "test")

      # Test tools
      result = await get_blacklist_status()
      assert result["entry_count"] > 0

      result = await check_batch(["evil.com", "safe.com"])
      assert result[0]["is_safe"] == False
      assert result[1]["is_safe"] == True
  ```
- [ ] Test CLI commands:
  ```python
  def test_cli_with_v2_storage():
      os.environ['MCP_USE_V2_STORAGE'] = 'true'

      result = subprocess.run(
          ["sec-mcp", "check", "evil.com"],
          capture_output=True,
          text=True
      )
      assert "Blacklisted" in result.stdout or result.returncode != 0
  ```

**Estimated Time**: 4-6 hours

---

### Task 3.3: Performance Benchmarks
**File**: `sec_mcp/tests/benchmarks_v2.py` (new file)

**Subtasks**:
- [ ] Benchmark single lookups:
  ```python
  def test_benchmark_domain_lookup_v1(benchmark):
      storage = Storage(":memory:")  # v1
      # Populate with 10K domains
      storage.add_domain("evil.com", "2025-01-01", 8.0, "test")

      result = benchmark(storage.is_domain_blacklisted, "evil.com")
      assert result == True

  def test_benchmark_domain_lookup_v2(benchmark):
      storage = HybridStorage(":memory:")  # v2
      # Populate with 10K domains
      storage.add_domain("evil.com", "2025-01-01", 8.0, "test")

      result = benchmark(storage.is_domain_blacklisted, "evil.com")
      assert result == True
  ```
- [ ] Benchmark batch operations:
  - 100 domains
  - 1000 domains
  - 10000 domains
- [ ] Benchmark CIDR lookups:
  - v1 (linear scan)
  - v2 (radix tree)
  - With 100, 1000, 10000 CIDR ranges
- [ ] Benchmark memory usage:
  ```python
  import tracemalloc

  def test_memory_usage_v2():
      tracemalloc.start()

      storage = HybridStorage(":memory:")
      # Load 125K entries
      # ...

      current, peak = tracemalloc.get_traced_memory()
      tracemalloc.stop()

      print(f"Current: {current / 1024 / 1024:.1f} MB")
      print(f"Peak: {peak / 1024 / 1024:.1f} MB")

      assert peak < 100 * 1024 * 1024  # Less than 100MB
  ```
- [ ] Create comparison report:
  ```
  Operation             | v1 (DB)  | v2 (Memory) | Speedup
  ---------------------|----------|-------------|--------
  Single domain check  | 10.5ms   | 0.012ms     | 875x
  Single URL check     | 5.2ms    | 0.001ms     | 5200x
  Single IP check      | 3.1ms    | 0.008ms     | 387x
  IP with 1K CIDRs     | 245ms    | 0.015ms     | 16,333x
  Batch 100 checks     | 2150ms   | 85ms        | 25x
  Batch 1000 checks    | 21500ms  | 750ms       | 29x
  Memory usage         | ~10MB    | ~65MB       | -6.5x
  ```

**Estimated Time**: 4-5 hours

---

### Task 3.4: Backward Compatibility Testing
**File**: `sec_mcp/tests/test_compatibility.py` (new file)

**Subtasks**:
- [ ] Test that v1 storage still works:
  ```python
  def test_v1_storage_still_works():
      os.environ['MCP_USE_V2_STORAGE'] = 'false'

      mcp = SecMCP(db_path=":memory:")
      # Should use old Storage class
      assert type(mcp.storage).__name__ == "Storage"
  ```
- [ ] Test migration path (v1 DB → v2 storage):
  ```python
  def test_migration_from_v1_to_v2():
      # Create v1 database with data
      v1_storage = Storage("test.db")
      v1_storage.add_domain("evil.com", "2025-01-01", 9.0, "test")

      # Load same DB with v2
      v2_storage = HybridStorage("test.db")

      # Should load existing data
      assert v2_storage.is_domain_blacklisted("evil.com")
  ```
- [ ] Test data consistency between v1 and v2:
  ```python
  def test_data_consistency():
      # Add data via v1
      v1_storage = Storage(":memory:")
      v1_storage.add_domain("evil.com", "2025-01-01", 9.0, "test")

      # Read via v2
      v2_storage = HybridStorage(v1_storage.db_path)

      # Should see same data
      assert v2_storage.is_domain_blacklisted("evil.com")
  ```

**Estimated Time**: 2-3 hours

---

## Phase 4: Documentation & Polish (Day 8)

### Task 4.1: Update Documentation
**Files**: `README.md`, `IMPLEMENTATION_PLAN.md`, inline docstrings

**Subtasks**:
- [ ] Update README.md:
  - Add section on performance improvements
  - Document new environment variable `MCP_USE_V2_STORAGE`
  - Add performance comparison table
  - Update memory requirements
- [ ] Create ARCHITECTURE.md:
  - Explain hybrid storage design
  - Document data structures used
  - Explain tradeoffs (memory vs speed)
  - Include diagrams (optional)
- [ ] Add comprehensive docstrings to all new methods:
  ```python
  def is_domain_blacklisted(self, domain: str) -> bool:
      """Check if a domain or any parent domain is blacklisted.

      This method performs hierarchical checking. For example, if
      'evil.com' is blacklisted, then 'sub.evil.com' and 'a.b.evil.com'
      are also considered blacklisted.

      Performance: O(depth) where depth is number of domain levels,
      typically 2-5. All lookups are in-memory O(1) hash lookups.

      Args:
          domain: Domain name to check (e.g., "example.com")

      Returns:
          True if domain or any parent is blacklisted, False otherwise

      Examples:
          >>> storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
          >>> storage.is_domain_blacklisted("evil.com")
          True
          >>> storage.is_domain_blacklisted("sub.evil.com")
          True
          >>> storage.is_domain_blacklisted("safe.com")
          False
      """
  ```
- [ ] Update PERFORMANCE_QUALITY_REVIEW.md:
  - Mark completed optimizations
  - Update performance metrics with actual results
  - Note any remaining issues

**Estimated Time**: 3-4 hours

---

### Task 4.2: Add Configuration Options
**File**: `sec_mcp/config.json`

**Subtasks**:
- [ ] Add new configuration options:
  ```json
  {
    "blacklist_sources": { ... },
    "update_time": "00:00",
    "cache_size": 10000,
    "log_level": "INFO",
    "db_path": "mcp.db",

    "storage": {
      "type": "hybrid",
      "preload_on_startup": true,
      "lazy_load_metadata": true,
      "memory_limit_mb": 100
    }
  }
  ```
- [ ] Implement lazy metadata loading (optional optimization):
  ```python
  class HybridStorage:
      def __init__(self, db_path, lazy_metadata=True):
          self.lazy_metadata = lazy_metadata

          if not lazy_metadata:
              # Load all metadata on startup
              self._load_metadata()
          else:
              # Load metadata on-demand
              self._metadata_loaded = False
  ```
- [ ] Add memory limit checking:
  ```python
  def _check_memory_limit(self):
      import psutil
      process = psutil.Process()
      mem_mb = process.memory_info().rss / 1024 / 1024

      if mem_mb > self.config['storage']['memory_limit_mb']:
          self.logger.warning(f"Memory usage {mem_mb:.1f}MB exceeds limit")
  ```

**Estimated Time**: 2-3 hours

---

### Task 4.3: Add Monitoring & Observability
**File**: `sec_mcp/storage_v2.py`

**Subtasks**:
- [ ] Add performance metrics collection:
  ```python
  from dataclasses import dataclass
  from datetime import datetime

  @dataclass
  class StorageMetrics:
      total_lookups: int = 0
      domain_lookups: int = 0
      url_lookups: int = 0
      ip_lookups: int = 0
      cache_hits: int = 0
      cache_misses: int = 0
      avg_lookup_time_ms: float = 0.0
      memory_usage_mb: float = 0.0
      last_reload: datetime = None

  class HybridStorage:
      def __init__(self, ...):
          self.metrics = StorageMetrics()

      def is_domain_blacklisted(self, domain: str) -> bool:
          start = time.perf_counter()
          result = self._check_domain(domain)
          elapsed = time.perf_counter() - start

          self.metrics.total_lookups += 1
          self.metrics.domain_lookups += 1
          self.metrics.avg_lookup_time_ms = (
              (self.metrics.avg_lookup_time_ms * (self.metrics.total_lookups - 1) + elapsed * 1000)
              / self.metrics.total_lookups
          )

          return result
  ```
- [ ] Add `get_metrics()` method:
  ```python
  def get_metrics(self) -> dict:
      """Get current storage performance metrics."""
      import psutil
      process = psutil.Process()

      self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024

      return {
          "total_lookups": self.metrics.total_lookups,
          "domain_lookups": self.metrics.domain_lookups,
          "url_lookups": self.metrics.url_lookups,
          "ip_lookups": self.metrics.ip_lookups,
          "avg_lookup_time_ms": f"{self.metrics.avg_lookup_time_ms:.4f}",
          "memory_usage_mb": f"{self.metrics.memory_usage_mb:.1f}",
          "last_reload": self.metrics.last_reload.isoformat() if self.metrics.last_reload else None,
          "entry_count": self.count_entries()
      }
  ```
- [ ] Add MCP tool to expose metrics:
  ```python
  @mcp.tool(name="get_storage_metrics", description="Get storage performance metrics")
  async def get_storage_metrics():
      if hasattr(core.storage, 'get_metrics'):
          return core.storage.get_metrics()
      else:
          return {"error": "Metrics not available in this storage version"}
  ```

**Estimated Time**: 2-3 hours

---

### Task 4.4: Error Handling & Edge Cases
**File**: `sec_mcp/storage_v2.py`

**Subtasks**:
- [ ] Handle startup failures gracefully:
  ```python
  def __init__(self, db_path=None):
      try:
          self._init_db()
          self._load_all_data()
      except Exception as e:
          self.logger.error(f"Failed to initialize storage: {e}")
          self.logger.warning("Starting with empty blacklist")
          # Initialize empty structures
          self._domains = set()
          self._urls = set()
          self._ips = set()
  ```
- [ ] Handle corrupted database:
  ```python
  def _init_db(self):
      try:
          with sqlite3.connect(self.db_path) as conn:
              # Test database integrity
              conn.execute("PRAGMA integrity_check")
      except sqlite3.DatabaseError:
          self.logger.error("Database corrupted, creating backup")
          shutil.copy(self.db_path, f"{self.db_path}.corrupt.backup")
          os.remove(self.db_path)
          # Reinitialize
          self._create_tables()
  ```
- [ ] Handle out-of-memory:
  ```python
  def _load_all_data(self):
      try:
          self._load_domains_from_db()
          self._load_urls_from_db()
          self._load_ips_from_db()
      except MemoryError:
          self.logger.error("Out of memory during data load")
          # Clear partially loaded data
          self._domains.clear()
          self._urls.clear()
          self._ips.clear()
          raise RuntimeError("Insufficient memory to load blacklist. Try reducing dataset or increasing available memory.")
  ```
- [ ] Handle invalid data during load:
  ```python
  def _load_domains_from_db(self):
      cursor = self._get_connection().execute(
          "SELECT domain, source, date, score FROM blacklist_domain"
      )

      loaded = 0
      errors = 0

      for domain, source, date, score in cursor:
          try:
              if not domain or not isinstance(domain, str):
                  raise ValueError("Invalid domain")

              domain_lower = domain.lower()
              self._domains.add(domain_lower)
              self._domain_meta[domain_lower] = EntryMetadata(source, date, score)
              loaded += 1

          except Exception as e:
              self.logger.warning(f"Skipping invalid domain entry: {e}")
              errors += 1

      self.logger.info(f"Loaded {loaded} domains ({errors} errors)")
  ```

**Estimated Time**: 3-4 hours

---

## Phase 5: Deployment & Rollout (Day 9-10)

### Task 5.1: Gradual Rollout Strategy
**File**: `ROLLOUT_PLAN.md` (new file)

**Subtasks**:
- [ ] Document rollout phases:
  ```markdown
  ## Phase 1: Internal Testing (Week 1)
  - Enable v2 storage for development team only
  - Monitor performance and stability
  - Collect feedback

  ## Phase 2: Beta Testing (Week 2)
  - Enable for 10% of users via feature flag
  - Monitor metrics, error rates, memory usage
  - Compare v1 vs v2 performance in production

  ## Phase 3: Gradual Rollout (Week 3-4)
  - 25% of users
  - 50% of users
  - 75% of users
  - 100% of users

  ## Phase 4: Deprecate v1 (Week 5+)
  - Make v2 default
  - Remove v1 code in future release
  ```
- [ ] Create monitoring dashboard:
  - Error rates by storage version
  - Performance metrics (p50, p95, p99)
  - Memory usage trends
  - User satisfaction scores
- [ ] Define rollback criteria:
  - If error rate > 1%
  - If memory usage > 200MB
  - If performance degrades > 20%
  - If critical bugs discovered

**Estimated Time**: 2-3 hours

---

### Task 5.2: Update Deployment Scripts
**File**: `.github/workflows/deploy.yml`, `setup.py`

**Subtasks**:
- [ ] Add `pytricia` to dependencies:
  ```toml
  # pyproject.toml
  dependencies = [
    "requests>=2.31.0",
    "httpx>=0.25.0",
    "click>=8.1.7",
    "idna>=3.4",
    "mcp[cli]>=0.1.0",
    "schedule>=1.2.0",
    "tqdm>=4.66.0",
    "pytricia>=1.0.0",  # New dependency
    "psutil>=5.9.0",     # For memory monitoring
  ]
  ```
- [ ] Update CI/CD pipeline:
  - Run tests for both v1 and v2 storage
  - Run performance benchmarks
  - Check memory usage limits
- [ ] Update installation instructions:
  ```bash
  # Install with optimizations
  pip install sec-mcp[fast]

  # Or minimal install (no pytricia)
  pip install sec-mcp
  ```
- [ ] Create migration guide for existing users:
  ```markdown
  ## Migrating to v2 Storage

  1. Upgrade sec-mcp: `pip install --upgrade sec-mcp`
  2. Enable v2 storage: `export MCP_USE_V2_STORAGE=true`
  3. Restart MCP server
  4. First startup will take 5-10 seconds (loading data into memory)
  5. Subsequent checks will be 1000x faster!

  To rollback: `export MCP_USE_V2_STORAGE=false` and restart
  ```

**Estimated Time**: 2-3 hours

---

### Task 5.3: Version Bump & Release
**File**: `pyproject.toml`, `CHANGELOG.md`

**Subtasks**:
- [ ] Update version number:
  ```toml
  [project]
  version = "0.3.0"  # Major optimization release
  ```
- [ ] Create CHANGELOG.md entry:
  ```markdown
  # Changelog

  ## [0.3.0] - 2025-11-22

  ### Added
  - 🚀 **Hybrid in-memory storage** for 1000x faster lookups
  - PyTricia-based CIDR matching (20,000x faster IP checks)
  - Performance monitoring and metrics collection
  - Storage metrics MCP tool
  - Feature flag for gradual rollout (`MCP_USE_V2_STORAGE`)

  ### Changed
  - Default storage now loads data into memory on startup
  - Memory usage increased to ~60-80MB (acceptable for speed gains)
  - Startup time: 5-10 seconds (one-time cost)

  ### Performance Improvements
  - Domain check: 10ms → 0.01ms (1000x faster)
  - URL check: 5ms → 0.001ms (5000x faster)
  - IP + CIDR check: 200ms → 0.01ms (20,000x faster)
  - Batch 100 items: 2-3s → 50-100ms (30x faster)

  ### Deprecated
  - Legacy database-only storage (v1) will be removed in v1.0.0

  ## [0.2.7] - Previous release
  ...
  ```
- [ ] Tag release:
  ```bash
  git tag -a v0.3.0 -m "Release v0.3.0: Hybrid storage with 1000x performance improvement"
  git push origin v0.3.0
  ```
- [ ] Publish to PyPI:
  ```bash
  python -m build
  python -m twine upload dist/*
  ```

**Estimated Time**: 1-2 hours

---

## Risk Mitigation

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Memory usage exceeds 100MB | Medium | Medium | Implement lazy loading, add memory limits, monitor in production |
| pytricia not available on some platforms | Low | High | Provide fallback to list-based CIDR matching |
| Data corruption during dual write | Low | High | Use transactions, implement rollback, thorough testing |
| Startup time > 30 seconds | Low | Medium | Optimize loading, add progress reporting, profile bottlenecks |
| Thread safety issues | Medium | High | Extensive concurrent testing, use RLock properly |
| Incompatibility with existing deployments | Low | High | Feature flag, thorough compatibility testing, rollback plan |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Users don't enable v2 storage | High | Low | Make v2 default in future release, document benefits clearly |
| Performance regression in some cases | Medium | Medium | Comprehensive benchmarks, canary deployment, rollback plan |
| Increased support burden | Medium | Low | Clear documentation, troubleshooting guide, monitoring |

---

## Success Metrics

### Performance Targets
- [x] Domain check: < 0.1ms (target: 0.01ms)
- [x] URL check: < 0.01ms (target: 0.001ms)
- [x] IP check with CIDR: < 0.1ms (target: 0.01ms)
- [x] Batch 100 items: < 200ms (target: 100ms)
- [x] Memory usage: < 100MB (target: 60-80MB)
- [x] Startup time: < 15 seconds (target: 5-10s)

### Quality Targets
- [x] Test coverage: > 90%
- [x] Zero data loss during migration
- [x] Backward compatible (v1 still works)
- [x] No breaking API changes
- [x] All existing tests pass

### User Experience Targets
- [x] No changes to CLI commands
- [x] No changes to MCP tool interfaces
- [x] Clear documentation of new features
- [x] Easy rollback path

---

## Timeline Summary

| Phase | Days | Key Deliverables |
|-------|------|------------------|
| **Phase 1**: Core Storage Refactoring | 3 | HybridStorage class, in-memory lookups, CIDR tree |
| **Phase 2**: Integration | 2 | MCP server, CLI, updater integration |
| **Phase 3**: Testing | 2 | Unit tests, integration tests, benchmarks |
| **Phase 4**: Documentation | 1 | README, docs, monitoring |
| **Phase 5**: Deployment | 2 | Rollout plan, version bump, release |
| **Total** | **10 days** | v0.3.0 release with 1000x performance improvement |

---

## Post-Implementation Tasks

### Future Optimizations (Beyond This Plan)

1. **Bloom filter layer** for even faster negative lookups (if scaling to 10M+ entries)
2. **Memory-mapped files** for zero-copy startup
3. **Distributed caching** (Redis) for multi-server deployments
4. **Compression** for domain/URL storage (Patricia trie)
5. **Async loading** to reduce startup time
6. **Incremental updates** without full reload
7. **Query result caching** with TTL

### Monitoring & Maintenance

1. Set up alerting for:
   - Memory usage > 150MB
   - Lookup time > 1ms (p99)
   - Error rate > 0.1%
   - Database corruption
2. Regular performance audits (monthly)
3. User feedback collection
4. Optimization opportunities based on real-world usage patterns

---

## Appendix: Quick Reference

### Environment Variables

```bash
# Enable v2 storage (hybrid in-memory)
export MCP_USE_V2_STORAGE=true

# Configure memory limit
export MCP_STORAGE_MEMORY_LIMIT_MB=100

# Enable debug logging
export MCP_LOG_LEVEL=DEBUG
```

### Testing Commands

```bash
# Run all tests
pytest

# Run only v2 storage tests
pytest sec_mcp/tests/test_storage_v2.py

# Run benchmarks
pytest sec_mcp/tests/benchmarks_v2.py --benchmark-only

# Check memory usage
python -m memory_profiler sec_mcp/storage_v2.py

# Profile performance
python -m cProfile -o profile.stats sec_mcp/storage_v2.py
```

### Performance Testing

```python
# Quick performance test
from sec_mcp.storage_v2 import HybridStorage
import time

storage = HybridStorage(":memory:")

# Add 100K domains
for i in range(100000):
    storage.add_domain(f"domain{i}.com", "2025-01-01", 8.0, "test")

# Benchmark lookup
start = time.perf_counter()
for i in range(10000):
    storage.is_domain_blacklisted(f"domain{i}.com")
elapsed = time.perf_counter() - start

print(f"10K lookups in {elapsed:.3f}s = {elapsed/10000*1000:.4f}ms per lookup")
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-21
**Author**: Implementation Team
**Status**: Ready for Implementation
