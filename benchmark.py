#!/usr/bin/env python3
"""
Benchmark script to compare different storage implementations.

Compares:
- v1: Original SQLite-based storage with simple caching
- v0.3.0: Hybrid in-memory + SQLite storage
- v0.4.0: Hybrid storage with tiered lookup and memory optimizations

Prerequisites:
    pip install pytricia psutil

Usage:
    python benchmark.py [--quick] [--full] [--memory]

Options:
    --quick     Run quick benchmark (10K entries, faster)
    --full      Run full benchmark (100K+ entries, production-like)
    --memory    Include memory profiling (requires psutil)
    --all       Run all benchmarks
"""

import sys
import os
import time
import tempfile
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any
import random
import string

# Check for required dependencies
def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []

    try:
        import pytricia
    except ImportError:
        missing.append('pytricia')

    try:
        import psutil
    except ImportError:
        missing.append('psutil')

    if missing:
        print("ERROR: Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print(f"\nInstall with: pip install {' '.join(missing)}")
        print("Or install all dependencies: pip install -e .")
        return False

    return True

# Add sec_mcp to path
sys.path.insert(0, str(Path(__file__).parent))

# Import storage modules directly to avoid dependency issues
import importlib.util

def import_storage_v1():
    """Import StorageV1 directly from file."""
    spec = importlib.util.spec_from_file_location("storage", Path(__file__).parent / "sec_mcp" / "storage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Storage

def import_storage_v2():
    """Import StorageV2 directly from file."""
    spec = importlib.util.spec_from_file_location("storage_v2", Path(__file__).parent / "sec_mcp" / "storage_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HybridStorage

try:
    StorageV1 = import_storage_v1()
except Exception as e:
    print(f"Warning: Could not import v1 storage: {e}")
    StorageV1 = None

try:
    StorageV2 = import_storage_v2()
except Exception as e:
    print(f"Warning: Could not import v2 storage: {e}")
    StorageV2 = None


class BenchmarkResults:
    """Store and display benchmark results."""

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}

    def add_result(self, version: str, operation: str, time_ms: float, **kwargs):
        """Add a benchmark result."""
        if version not in self.results:
            self.results[version] = {}
        self.results[version][operation] = {
            'time_ms': time_ms,
            **kwargs
        }

    def add_memory(self, version: str, memory_mb: float):
        """Add memory usage result."""
        if version not in self.results:
            self.results[version] = {}
        self.results[version]['memory_mb'] = memory_mb

    def print_comparison(self):
        """Print formatted comparison table."""
        print("\n" + "="*80)
        print("BENCHMARK RESULTS COMPARISON")
        print("="*80)

        # Get all operations
        all_ops = set()
        for version_results in self.results.values():
            all_ops.update(version_results.keys())
        all_ops.discard('memory_mb')

        # Print table header
        print(f"\n{'Operation':<25} {'v1 (DB)':<15} {'v0.3.0 (Hybrid)':<20} {'v0.4.0 (Optimized)':<20} {'Speedup':<15}")
        print("-" * 100)

        # Print each operation
        for op in sorted(all_ops):
            v1_time = self.results.get('v1', {}).get(op, {}).get('time_ms', 0)
            v2_time = self.results.get('v0.3.0', {}).get(op, {}).get('time_ms', 0)
            v2opt_time = self.results.get('v0.4.0', {}).get(op, {}).get('time_ms', 0)

            if v1_time > 0 and v2opt_time > 0:
                speedup = f"{v1_time / v2opt_time:.1f}x"
            else:
                speedup = "N/A"

            v1_str = f"{v1_time:.4f}ms" if v1_time > 0 else "N/A"
            v2_str = f"{v2_time:.4f}ms" if v2_time > 0 else "N/A"
            v2opt_str = f"{v2opt_time:.4f}ms" if v2opt_time > 0 else "N/A"

            print(f"{op:<25} {v1_str:<15} {v2_str:<20} {v2opt_str:<20} {speedup:<15}")

        # Print memory usage
        print("\n" + "-" * 100)
        print(f"{'Memory Usage':<25} ", end="")
        for version in ['v1', 'v0.3.0', 'v0.4.0']:
            mem = self.results.get(version, {}).get('memory_mb', 0)
            if mem > 0:
                print(f"{mem:.1f}MB{' '*9} ", end="")
            else:
                print(f"{'N/A':<15} ", end="")
        print()

        # Print optimization metrics for v0.4.0
        if 'v0.4.0' in self.results:
            v4_results = self.results['v0.4.0']
            if 'hot_hit_rate' in v4_results.get('domain_lookup', {}):
                print("\n" + "="*80)
                print("v0.4.0 OPTIMIZATION METRICS")
                print("="*80)
                for op in ['domain_lookup', 'url_lookup', 'ip_lookup']:
                    if op in v4_results and 'hot_hit_rate' in v4_results[op]:
                        rate = v4_results[op]['hot_hit_rate']
                        print(f"{op.replace('_', ' ').title():<25} Hot source hit rate: {rate:.1f}%")

        print("\n" + "="*80 + "\n")


class BenchmarkData:
    """Generate realistic benchmark data matching production distribution."""

    @staticmethod
    def random_domain(length=10):
        """Generate random domain name."""
        name = ''.join(random.choices(string.ascii_lowercase, k=length))
        tld = random.choice(['com', 'net', 'org', 'ru', 'cn', 'info'])
        return f"{name}.{tld}"

    @staticmethod
    def random_url(domain=None):
        """Generate random URL."""
        if domain is None:
            domain = BenchmarkData.random_domain()
        path = ''.join(random.choices(string.ascii_lowercase, k=8))
        return f"http://{domain}/{path}"

    @staticmethod
    def random_ip():
        """Generate random IPv4 address."""
        return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

    @staticmethod
    def random_cidr():
        """Generate random CIDR range."""
        ip = BenchmarkData.random_ip()
        prefix = random.choice([24, 16, 8])
        return f"{ip}/{prefix}"

    @staticmethod
    def generate_production_like_data(total_entries=10000):
        """
        Generate data matching production distribution:
        - 449K total entries
        - PhishTank: 133K URLs (30%)
        - URLhaus: 74K URLs (16%)
        - BlocklistDE: 85K IPs (19%)
        - CINSSCORE: 41K IPs (9%)
        - PhishStats: 42K domains (9%)
        - Dshield: 33K IPs (7%)
        - EmergingThreats: 25K IPs (6%)
        - SpamhausDROP: 12K IPs (3%)
        - OpenPhish: 4K URLs (1%)
        """
        data = {
            'domains': [],
            'urls': [],
            'ips': [],
            'cidrs': []
        }

        # Distribution based on production data (normalized to total_entries)
        distributions = [
            ('PhishTank', 'url', 0.30),      # 133K/449K
            ('URLhaus', 'url', 0.16),        # 74K/449K
            ('BlocklistDE', 'ip', 0.19),     # 85K/449K
            ('CINSSCORE', 'ip', 0.09),       # 41K/449K
            ('PhishStats', 'domain', 0.09),  # 42K/449K
            ('Dshield', 'ip', 0.07),         # 33K/449K
            ('EmergingThreats', 'ip', 0.06), # 25K/449K
            ('SpamhausDROP', 'cidr', 0.03),  # 12K/449K
            ('OpenPhish', 'url', 0.01),      # 4K/449K
        ]

        for source, data_type, ratio in distributions:
            count = int(total_entries * ratio)

            for _ in range(count):
                entry = {
                    'source': source,
                    'date_added': '2025-01-01',
                    'confidence': random.uniform(7.0, 10.0)
                }

                if data_type == 'domain':
                    entry['value'] = BenchmarkData.random_domain()
                    data['domains'].append(entry)
                elif data_type == 'url':
                    entry['value'] = BenchmarkData.random_url()
                    data['urls'].append(entry)
                elif data_type == 'ip':
                    entry['value'] = BenchmarkData.random_ip()
                    data['ips'].append(entry)
                elif data_type == 'cidr':
                    entry['value'] = BenchmarkData.random_cidr()
                    data['cidrs'].append(entry)

        return data


class StorageBenchmark:
    """Benchmark a storage implementation."""

    def __init__(self, storage, version_name: str):
        self.storage = storage
        self.version = version_name
        self.results = BenchmarkResults()

    def load_data(self, data: Dict[str, List[Dict]]):
        """Load test data into storage."""
        print(f"  Loading {sum(len(v) for v in data.values())} entries into {self.version}...", end=" ", flush=True)
        start = time.perf_counter()

        for domain_entry in data['domains']:
            self.storage.add_domain(
                domain_entry['value'],
                domain_entry['date_added'],
                domain_entry['confidence'],
                domain_entry['source']
            )

        for url_entry in data['urls']:
            self.storage.add_url(
                url_entry['value'],
                url_entry['date_added'],
                url_entry['confidence'],
                url_entry['source']
            )

        for ip_entry in data['ips']:
            self.storage.add_ip(
                ip_entry['value'],
                ip_entry['date_added'],
                ip_entry['confidence'],
                ip_entry['source']
            )

        for cidr_entry in data['cidrs']:
            self.storage.add_cidr(
                cidr_entry['value'],
                cidr_entry['date_added'],
                cidr_entry['confidence'],
                cidr_entry['source']
            )

        elapsed = time.perf_counter() - start
        print(f"Done in {elapsed:.2f}s")
        self.results.add_result(self.version, 'data_load', elapsed * 1000)

    def benchmark_lookups(self, data: Dict[str, List[Dict]], iterations=1000):
        """Benchmark lookup operations."""
        print(f"  Running {iterations} lookup iterations for {self.version}...")

        # Domain lookups
        if data['domains']:
            test_domains = random.sample(data['domains'], min(iterations, len(data['domains'])))
            start = time.perf_counter()
            for entry in test_domains:
                self.storage.is_domain_blacklisted(entry['value'])
            elapsed = (time.perf_counter() - start) / len(test_domains)

            metrics = {}
            if isinstance(self.storage, StorageV2):
                storage_metrics = self.storage.get_metrics()
                if 'hot_source_hits' in storage_metrics and 'cold_source_hits' in storage_metrics:
                    total_hits = storage_metrics['hot_source_hits'] + storage_metrics['cold_source_hits']
                    if total_hits > 0:
                        metrics['hot_hit_rate'] = (storage_metrics['hot_source_hits'] / total_hits) * 100

            self.results.add_result(self.version, 'domain_lookup', elapsed * 1000, **metrics)
            print(f"    Domain lookup: {elapsed * 1000:.4f}ms")

        # URL lookups
        if data['urls']:
            test_urls = random.sample(data['urls'], min(iterations, len(data['urls'])))
            start = time.perf_counter()
            for entry in test_urls:
                self.storage.is_url_blacklisted(entry['value'])
            elapsed = (time.perf_counter() - start) / len(test_urls)

            metrics = {}
            if isinstance(self.storage, StorageV2):
                storage_metrics = self.storage.get_metrics()
                if 'hot_source_hits' in storage_metrics and 'cold_source_hits' in storage_metrics:
                    total_hits = storage_metrics['hot_source_hits'] + storage_metrics['cold_source_hits']
                    if total_hits > 0:
                        metrics['hot_hit_rate'] = (storage_metrics['hot_source_hits'] / total_hits) * 100

            self.results.add_result(self.version, 'url_lookup', elapsed * 1000, **metrics)
            print(f"    URL lookup: {elapsed * 1000:.4f}ms")

        # IP lookups
        if data['ips']:
            test_ips = random.sample(data['ips'], min(iterations, len(data['ips'])))
            start = time.perf_counter()
            for entry in test_ips:
                self.storage.is_ip_blacklisted(entry['value'])
            elapsed = (time.perf_counter() - start) / len(test_ips)

            metrics = {}
            if isinstance(self.storage, StorageV2):
                storage_metrics = self.storage.get_metrics()
                if 'hot_source_hits' in storage_metrics and 'cold_source_hits' in storage_metrics:
                    total_hits = storage_metrics['hot_source_hits'] + storage_metrics['cold_source_hits']
                    if total_hits > 0:
                        metrics['hot_hit_rate'] = (storage_metrics['hot_source_hits'] / total_hits) * 100

            self.results.add_result(self.version, 'ip_lookup', elapsed * 1000, **metrics)
            print(f"    IP lookup: {elapsed * 1000:.4f}ms")

        # CIDR lookups (IP in range)
        if data['cidrs'] and data['ips']:
            test_ips = random.sample(data['ips'], min(iterations, len(data['ips'])))
            start = time.perf_counter()
            for entry in test_ips:
                self.storage.is_ip_blacklisted(entry['value'])  # Will check CIDR ranges too
            elapsed = (time.perf_counter() - start) / len(test_ips)
            self.results.add_result(self.version, 'cidr_lookup', elapsed * 1000)
            print(f"    CIDR lookup: {elapsed * 1000:.4f}ms")

        # Batch lookups
        if data['ips']:
            batch_size = 100
            test_batch = random.sample(data['ips'], min(batch_size, len(data['ips'])))
            start = time.perf_counter()
            for entry in test_batch:
                self.storage.is_ip_blacklisted(entry['value'])
            elapsed = time.perf_counter() - start
            self.results.add_result(self.version, f'batch_{batch_size}', elapsed * 1000)
            print(f"    Batch {batch_size} items: {elapsed * 1000:.2f}ms")

    def benchmark_memory(self):
        """Estimate memory usage."""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            self.results.add_memory(self.version, mem_mb)
            print(f"    Memory usage: {mem_mb:.1f}MB")
        except ImportError:
            print(f"    Memory profiling skipped (psutil not installed)")


def run_benchmark(args):
    """Run complete benchmark suite."""
    print("\n" + "="*80)
    print("STORAGE BENCHMARK")
    print("="*80)

    # Determine data size
    if args.quick:
        data_size = 10000
        iterations = 500
        print(f"Mode: QUICK (10K entries, 500 iterations)")
    elif args.full:
        data_size = 100000
        iterations = 1000
        print(f"Mode: FULL (100K entries, 1000 iterations)")
    else:
        data_size = 50000
        iterations = 1000
        print(f"Mode: STANDARD (50K entries, 1000 iterations)")

    # Generate test data
    print(f"\nGenerating {data_size} test entries with production-like distribution...")
    data = BenchmarkData.generate_production_like_data(data_size)
    print(f"  Domains: {len(data['domains'])}")
    print(f"  URLs: {len(data['urls'])}")
    print(f"  IPs: {len(data['ips'])}")
    print(f"  CIDRs: {len(data['cidrs'])}")

    all_results = BenchmarkResults()

    # Benchmark v1 (original database storage)
    if args.all or args.v1:
        if StorageV1 is None:
            print("\n" + "-"*80)
            print("SKIPPING v1 (Database Storage) - Could not import")
            print("-"*80)
        else:
            print("\n" + "-"*80)
            print("BENCHMARKING v1 (Database Storage)")
            print("-"*80)
            # Create a temporary directory for the database
            tmp_dir = tempfile.mkdtemp(prefix='sec_mcp_bench_v1_')
            tmp_path = os.path.join(tmp_dir, 'benchmark.db')
            try:
                storage_v1 = StorageV1(tmp_path)
                bench_v1 = StorageBenchmark(storage_v1, 'v1')
                bench_v1.load_data(data)
                bench_v1.benchmark_lookups(data, iterations)
                if args.memory:
                    bench_v1.benchmark_memory()

                # Merge results
                for version, results in bench_v1.results.results.items():
                    all_results.results[version] = results
            finally:
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except:
                    pass

    # Benchmark v0.3.0 (hybrid storage)
    if args.all or args.v2:
        if StorageV2 is None:
            print("\n" + "-"*80)
            print("SKIPPING v0.3.0 (Hybrid Storage) - Could not import")
            print("-"*80)
        else:
            print("\n" + "-"*80)
            print("BENCHMARKING v0.3.0 (Hybrid Storage)")
            print("-"*80)
            # Create a temporary directory for the database
            tmp_dir = tempfile.mkdtemp(prefix='sec_mcp_bench_v2_')
            tmp_path = os.path.join(tmp_dir, 'benchmark.db')
            try:
                storage_v2 = StorageV2(tmp_path)
                bench_v2 = StorageBenchmark(storage_v2, 'v0.3.0')
                bench_v2.load_data(data)
                bench_v2.benchmark_lookups(data, iterations)
                if args.memory:
                    bench_v2.benchmark_memory()

                # Merge results
                for version, results in bench_v2.results.results.items():
                    all_results.results[version] = results
            finally:
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except:
                    pass

    # Benchmark v0.4.0 (optimized hybrid storage)
    if args.all or args.v2opt:
        if StorageV2 is None:
            print("\n" + "-"*80)
            print("SKIPPING v0.4.0 (Optimized Hybrid Storage) - Could not import")
            print("-"*80)
        else:
            print("\n" + "-"*80)
            print("BENCHMARKING v0.4.0 (Optimized Hybrid Storage)")
            print("-"*80)
            # Create a temporary directory for the database
            tmp_dir = tempfile.mkdtemp(prefix='sec_mcp_bench_v2opt_')
            tmp_path = os.path.join(tmp_dir, 'benchmark.db')
            try:
                storage_v2opt = StorageV2(tmp_path)
                bench_v2opt = StorageBenchmark(storage_v2opt, 'v0.4.0')
                bench_v2opt.load_data(data)
                bench_v2opt.benchmark_lookups(data, iterations)
                if args.memory:
                    bench_v2opt.benchmark_memory()

                # Merge results
                for version, results in bench_v2opt.results.results.items():
                    all_results.results[version] = results
            finally:
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except:
                    pass

    # Print comparison
    all_results.print_comparison()

    # Save results to file
    output_file = 'benchmark_results.txt'
    print(f"Results saved to: {output_file}")


def main():
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description='Benchmark sec-mcp storage implementations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmark.py --quick              # Quick test with 10K entries
  python benchmark.py --full --memory      # Full test with memory profiling
  python benchmark.py --all                # Compare all versions
  python benchmark.py --v2 --v2opt         # Compare only v0.3.0 and v0.4.0
        """
    )

    # Data size options
    parser.add_argument('--quick', action='store_true',
                        help='Quick benchmark (10K entries, faster)')
    parser.add_argument('--full', action='store_true',
                        help='Full benchmark (100K entries, production-like)')

    # Version selection
    parser.add_argument('--all', action='store_true',
                        help='Benchmark all versions (v1, v0.3.0, v0.4.0)')
    parser.add_argument('--v1', action='store_true',
                        help='Benchmark v1 only')
    parser.add_argument('--v2', action='store_true',
                        help='Benchmark v0.3.0 only')
    parser.add_argument('--v2opt', action='store_true',
                        help='Benchmark v0.4.0 only')

    # Additional options
    parser.add_argument('--memory', action='store_true',
                        help='Include memory profiling (requires psutil)')

    args = parser.parse_args()

    # Default: benchmark v2 and v2opt
    if not (args.all or args.v1 or args.v2 or args.v2opt):
        args.v2 = True
        args.v2opt = True

    run_benchmark(args)


if __name__ == '__main__':
    main()
