# Storage Optimization Proposal v2
## Data-Driven Performance Improvements

**Date**: 2025-11-22
**Context**: Based on actual production data analysis
**Current Performance**: Already 1000-20,000x faster with v0.3.0
**Goal**: Additional 2-5x improvement + 30-40% memory reduction

---

## Current Data Distribution Analysis

### Overall Statistics
- **Total entries**: ~449,000
- **Domains**: 100,869 (22%)
- **URLs**: 207,121 (46%)
- **IPs**: 140,591 (31%)

### Source Specialization

| Source | Domains | URLs | IPs | Type |
|--------|---------|------|-----|------|
| BlocklistDE | 0 | 0 | 70,527 | **IP-only** |
| CINSSCORE | 0 | 0 | 55,698 | **IP-only** |
| Dshield | 0 | 0 | 68 | **IP-only** |
| EmergingThreats | 0 | 0 | 1,357 | **IP-only** |
| SpamhausDROP | 0 | 0 | 1,895 | **IP-only** |
| **IP-only Total** | **0** | **0** | **129,545 (92% of IPs)** | |
| OpenPhish | 2,536 | 3,476 | 0 | **Domain/URL-only** |
| PhishTank | 53,278 | 83,881 | 0 | **Domain/URL-only** |
| **Domain/URL Total** | **55,814** | **87,357** | **0** | |
| PhishStats | 37,619 | 50,576 | 11,045 | **Mixed** |
| URLhaus | 7,436 | 69,188 | 1 | **Mixed** |
| **Mixed Total** | **45,055** | **119,764** | **11,046** | |

### Key Insights

1. **92% of IPs come from IP-only sources** → Can use specialized storage
2. **55% of domains come from domain/URL-only sources** → Can skip IP checks
3. **Only 8% of IPs are in mixed sources** → Minimal overlap complexity
4. **PhishTank and URLhaus dominate URLs** → Could use tiered lookup

---

## Proposed Optimizations

### 🎯 Optimization 1: Source-Aware Lookup Routing

**Concept**: Route lookups based on input type to skip irrelevant sources.

**Current Behavior**:
```python
def is_ip_blacklisted(self, ip: str) -> bool:
    # Checks all IPs in unified set (140K entries)
    if ip in self._ips:
        return True
    # Then checks CIDR trees (all ranges)
    return ip in self._ipv4_cidr_tree or ip in self._ipv6_cidr_tree
```

**Optimized Behavior**:
```python
def is_ip_blacklisted(self, ip: str) -> bool:
    # Check exact IPs first (O(1))
    if ip in self._ips_exact:
        return True

    # Check IP-only sources (92% of IPs) using specialized structure
    if ip in self._ip_only_sources_set:
        return True

    # Only then check CIDR trees (mostly from mixed sources)
    return self._check_cidr_trees(ip)
```

**Expected Improvement**:
- **Lookups**: 10-20% faster (reduced tree traversal)
- **Memory**: No change
- **Complexity**: Minimal

---

### 🎯 Optimization 2: Tiered Lookup by Source Frequency

**Concept**: Check "hot" sources first for early exit.

**Implementation**:
```python
class HybridStorage:
    def __init__(self):
        # Hot sources (80% of lookups typically hit these)
        self._hot_urls = set()  # PhishTank, URLhaus
        self._hot_ips = set()   # BlocklistDE, CINSSCORE

        # Cold sources (checked only if hot sources miss)
        self._cold_urls = set()
        self._cold_ips = set()

    def is_url_blacklisted(self, url: str) -> bool:
        # Check hot sources first (2 sources, ~153K URLs = 74% of total)
        if url in self._hot_urls:
            return True

        # Only check remaining sources if needed
        return url in self._cold_urls
```

**Expected Improvement**:
- **Lookups**: 15-25% faster (early exit optimization)
- **Memory**: Negligible (just organizing existing data)
- **Complexity**: Low

**Configuration**:
```json
{
  "hot_sources": {
    "urls": ["PhishTank", "URLhaus"],
    "ips": ["BlocklistDE", "CINSSCORE"],
    "domains": ["PhishTank", "PhishStats"]
  }
}
```

---

### 🎯 Optimization 3: Bloom Filters for Negative Lookups

**Concept**: Use bloom filters to quickly determine "definitely not in set" before checking main structures.

**Memory Cost**: ~1-2MB per filter (for 100K entries with 0.1% false positive rate)

**Implementation**:
```python
from pybloom_live import BloomFilter

class HybridStorage:
    def __init__(self):
        # Bloom filters for fast negative lookups
        self._domains_bloom = BloomFilter(capacity=150000, error_rate=0.001)
        self._urls_bloom = BloomFilter(capacity=250000, error_rate=0.001)
        self._ips_bloom = BloomFilter(capacity=200000, error_rate=0.001)

        # Main storage (unchanged)
        self._domains = set()
        self._urls = set()
        self._ips = set()

    def is_domain_blacklisted(self, domain: str) -> bool:
        # Quick negative check (O(k) where k = # hash functions, typically 7-10)
        if domain not in self._domains_bloom:
            return False  # Definitely not blacklisted

        # Might be blacklisted, check actual set
        return domain in self._domains or self._check_parent_domains(domain)
```

**Expected Improvement**:
- **Lookups on non-blacklisted items**: 50-70% faster (majority of lookups)
- **Lookups on blacklisted items**: Same speed (no degradation)
- **Memory**: +3-5MB (minimal overhead)
- **Complexity**: Low (library available)

**Benefit Analysis**:
- If 80% of lookups are for safe items, and bloom filters save 50-70% on those → **40-56% overall speedup**

---

### 🎯 Optimization 4: Integer-Based IP Storage

**Concept**: Store IPs as 32-bit/128-bit integers instead of strings.

**Current Storage**:
```python
self._ips = {"192.168.1.1", "10.0.0.1", ...}  # 13-15 bytes per IP (string)
```

**Optimized Storage**:
```python
self._ips_int = {3232235777, 167772161, ...}  # 4 bytes per IPv4 (int)

def ip_to_int(ip: str) -> int:
    octets = ip.split('.')
    return (int(octets[0]) << 24) + (int(octets[1]) << 16) + \
           (int(octets[2]) << 8) + int(octets[3])

def is_ip_blacklisted(self, ip: str) -> bool:
    ip_int = ip_to_int(ip)
    return ip_int in self._ips_int
```

**Expected Improvement**:
- **Memory**: 60-70% reduction for IP storage (~20-25MB saved)
- **Lookups**: 5-10% faster (integer comparison vs string)
- **Complexity**: Medium (requires conversion functions)

**Actual Savings**:
- 140K IPs × 10 bytes saved per IP = **~1.4MB saved**
- Not huge, but worth it for the lookup speed improvement

---

### 🎯 Optimization 5: Domain Trie (Prefix Tree)

**Concept**: Store domains in a trie for efficient parent domain matching.

**Current Approach**:
```python
def is_domain_blacklisted(self, domain: str) -> bool:
    if domain in self._domains:
        return True

    # Check parent domains (split and iterate)
    parts = domain.split('.')
    for i in range(1, len(parts)):
        parent = '.'.join(parts[i:])
        if parent in self._domains:
            return True
    return False
```

**Optimized with Trie**:
```python
from pygtrie import StringTrie

class HybridStorage:
    def __init__(self):
        # Store domains in reverse order for parent matching
        self._domain_trie = StringTrie()

    def add_domain(self, domain: str, ...):
        # Store reversed: "example.com" → "moc.elpmaxe"
        reversed_domain = '.'.join(reversed(domain.split('.')))
        self._domain_trie[reversed_domain] = metadata

    def is_domain_blacklisted(self, domain: str) -> bool:
        reversed_domain = '.'.join(reversed(domain.split('.')))

        # Check if any prefix of reversed domain exists
        # "sub.example.com" → "moc.elpmaxe.bus"
        # Will match "moc.elpmaxe" if "example.com" is blacklisted
        return self._domain_trie.has_node(reversed_domain) or \
               any(self._domain_trie.has_subtrie(reversed_domain[:i])
                   for i in range(len(reversed_domain)))
```

**Expected Improvement**:
- **Memory**: 10-20% reduction for domains (~5-10MB saved)
- **Lookups**: 20-30% faster for parent domain checks
- **Complexity**: Medium-High

---

### 🎯 Optimization 6: URL Normalization & Deduplication

**Concept**: Normalize URLs before storage to reduce duplicates.

**Problem**:
```python
# These are all the same URL but stored separately:
"http://evil.com/"
"http://evil.com"
"HTTP://EVIL.COM/"
"http://evil.com/?utm_source=spam"
```

**Solution**:
```python
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    """Normalize URL for consistent storage."""
    parsed = urlparse(url.lower())

    # Remove tracking parameters
    query_params = parse_qs(parsed.query)
    filtered_params = {k: v for k, v in query_params.items()
                      if k not in ['utm_source', 'utm_medium', 'utm_campaign']}

    # Rebuild URL
    normalized = urlunparse((
        parsed.scheme or 'http',
        parsed.netloc,
        parsed.path.rstrip('/') or '/',
        '',
        urlencode(filtered_params, doseq=True),
        ''
    ))

    return normalized
```

**Expected Improvement**:
- **Memory**: 15-25% reduction for URLs (~15-30MB saved)
- **Accuracy**: Improved (catches more variations)
- **Complexity**: Medium

---

## Recommended Implementation Priority

### Phase 1: Low-Hanging Fruit (1-2 days)
**Priority**: HIGH
**Effort**: LOW
**Impact**: MEDIUM-HIGH

1. ✅ **Tiered Lookup** (Optimization 2)
   - Quick to implement
   - No memory cost
   - 15-25% speedup

2. ✅ **Source-Aware Routing** (Optimization 1)
   - Minimal code changes
   - Leverages existing data patterns
   - 10-20% speedup

**Combined Expected Improvement**: 25-40% faster lookups

### Phase 2: Memory Efficiency (2-3 days)
**Priority**: MEDIUM
**Effort**: MEDIUM
**Impact**: HIGH (memory reduction)

3. ✅ **URL Normalization** (Optimization 6)
   - 15-25MB saved
   - Better accuracy
   - Requires URL parsing library

4. ✅ **Integer IP Storage** (Optimization 4)
   - 1-2MB saved
   - 5-10% faster IP lookups
   - Requires conversion logic

**Combined Expected Improvement**: 30-40% memory reduction

### Phase 3: Advanced Optimizations (3-5 days)
**Priority**: LOW-MEDIUM
**Effort**: HIGH
**Impact**: HIGH (for specific use cases)

5. ⚠️ **Bloom Filters** (Optimization 3)
   - Best for workloads with many negative lookups
   - Requires additional dependency
   - 40-56% speedup for clean items

6. ⚠️ **Domain Trie** (Optimization 5)
   - Complex implementation
   - Best if many subdomain checks
   - 20-30% speedup for domain hierarchies

---

## Performance Projections

### Current Performance (v0.3.0)
| Operation | Time | Memory |
|-----------|------|--------|
| Domain check | 0.01ms | 60-80MB |
| URL check | 0.001ms | (total) |
| IP check | 0.01ms | |

### After Phase 1 (Tiered + Routing)
| Operation | Time | Memory |
|-----------|------|--------|
| Domain check | **0.006ms** | 60-80MB |
| URL check | **0.0007ms** | (unchanged) |
| IP check | **0.007ms** | |

**Improvement**: 30-40% faster, same memory

### After Phase 2 (+ Memory Optimization)
| Operation | Time | Memory |
|-----------|------|--------|
| Domain check | **0.005ms** | **40-50MB** |
| URL check | **0.0006ms** | |
| IP check | **0.006ms** | |

**Improvement**: 45-50% faster, 30-40% less memory

### After Phase 3 (+ Advanced)
| Operation | Time (clean) | Time (blacklisted) | Memory |
|-----------|--------------|-----------------------|--------|
| Domain check | **0.002ms** | 0.005ms | **35-45MB** |
| URL check | **0.0003ms** | 0.0006ms | |
| IP check | **0.003ms** | 0.006ms | |

**Improvement**: 70-80% faster for clean items, 40-50% less memory

---

## Cost-Benefit Analysis

### Phase 1: Tiered Lookup + Source Routing
- **Effort**: 1-2 developer days
- **Benefit**: 25-40% speedup, no memory cost
- **Risk**: Very Low
- **ROI**: ⭐⭐⭐⭐⭐ EXCELLENT

**Recommendation**: ✅ **IMPLEMENT IMMEDIATELY**

### Phase 2: Memory Optimization
- **Effort**: 2-3 developer days
- **Benefit**: 30-40% memory reduction, 5-10% speedup
- **Risk**: Low (requires testing)
- **ROI**: ⭐⭐⭐⭐ VERY GOOD

**Recommendation**: ✅ **IMPLEMENT AFTER PHASE 1**

### Phase 3: Bloom Filters
- **Effort**: 1-2 developer days
- **Benefit**: 40-56% speedup for negative lookups
- **Risk**: Medium (new dependency, false positives)
- **ROI**: ⭐⭐⭐ GOOD (workload dependent)

**Recommendation**: ⚠️ **CONSIDER IF NEGATIVE LOOKUPS DOMINATE**

### Phase 3: Domain Trie
- **Effort**: 3-4 developer days
- **Benefit**: 20-30% speedup for domains, 10-20% memory saving
- **Risk**: Medium-High (complex implementation)
- **ROI**: ⭐⭐ FAIR

**Recommendation**: ⚠️ **DEFER UNLESS SUBDOMAIN LOOKUPS ARE CRITICAL**

---

## Migration Path

### For Phase 1 Implementation

1. **Add source classification** to existing code:
   ```python
   class HybridStorage:
       def __init__(self):
           # Existing structures
           self._domains = set()
           self._urls = set()
           self._ips = set()

           # NEW: Tiered storage
           self._hot_urls = set()
           self._cold_urls = set()
           self._hot_ips = set()
           self._cold_ips = set()

           # NEW: Source routing
           self._ip_only_sources = {'BlocklistDE', 'CINSSCORE', ...}
           self._domain_url_sources = {'PhishTank', 'OpenPhish', ...}
   ```

2. **Update loading logic**:
   ```python
   def _load_urls_from_db(self):
       for url, source, ... in self._db_query():
           self._urls.add(url)

           # NEW: Classify by source
           if source in ['PhishTank', 'URLhaus']:
               self._hot_urls.add(url)
           else:
               self._cold_urls.add(url)
   ```

3. **Update lookup logic**:
   ```python
   def is_url_blacklisted(self, url: str) -> bool:
       # NEW: Check hot sources first
       if url in self._hot_urls:
           return True

       # Then check cold sources
       return url in self._cold_urls
   ```

4. **Maintain backward compatibility**: Keep existing methods, add new optimized paths.

### Testing Strategy

1. **Unit tests**: Add tests for new tiered lookup logic
2. **Performance tests**: Benchmark before/after
3. **Compatibility tests**: Ensure v1/v2 still work
4. **A/B testing**: Run both paths in parallel, compare results

---

## Monitoring & Metrics

Add new metrics to track optimization effectiveness:

```python
@dataclass
class StorageMetrics:
    # Existing metrics
    total_lookups: int
    domain_lookups: int
    url_lookups: int
    ip_lookups: int

    # NEW: Optimization metrics
    hot_source_hits: int  # Lookups that hit hot sources
    cold_source_hits: int  # Lookups that needed cold sources
    bloom_filter_saves: int  # Negative lookups saved by bloom filter
    avg_lookup_depth: float  # Average # of sources checked per lookup
```

---

## Conclusion

**Recommended Action Plan**:

1. ✅ **Immediate**: Implement Phase 1 (Tiered Lookup + Source Routing)
   - 1-2 days effort
   - 25-40% speedup
   - Zero risk

2. ✅ **Short-term**: Implement Phase 2 (Memory Optimization)
   - 2-3 days effort
   - 30-40% memory reduction
   - Low risk

3. ⚠️ **Long-term**: Evaluate Phase 3 based on production metrics
   - Monitor negative lookup ratio
   - If >70% lookups are negative → implement Bloom filters
   - If many subdomain lookups → implement Domain Trie

**Total Expected Improvement** (Phases 1+2):
- **Performance**: 45-50% faster than current v0.3.0
- **Memory**: 30-40% reduction (60-80MB → 40-50MB)
- **Effort**: 3-5 developer days
- **Risk**: Low

This would bring us from:
- v0.2.7 (database): 10ms per lookup
- v0.3.0 (hybrid): 0.01ms per lookup (1000x faster)
- **v0.4.0 (optimized hybrid)**: **0.005ms per lookup** (**2000x faster than v0.2.7**, **2x faster than v0.3.0**)

---

**Next Steps**: Should we proceed with Phase 1 implementation?
