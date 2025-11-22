"""Backward compatibility tests between v1 and v2 storage."""

import pytest
import os
import tempfile
from sec_mcp.storage import Storage, create_storage
from sec_mcp.storage_v2 import HybridStorage


class TestStorageFactory:
    """Test the storage factory function."""

    def test_factory_creates_v1_by_default(self):
        """Test that factory creates v1 storage by default."""
        os.environ.pop('MCP_USE_V2_STORAGE', None)  # Ensure not set

        storage = create_storage(":memory:")
        assert type(storage).__name__ == "Storage"

    def test_factory_creates_v2_when_enabled(self):
        """Test that factory creates v2 storage when enabled."""
        os.environ['MCP_USE_V2_STORAGE'] = 'true'

        storage = create_storage(":memory:")
        assert type(storage).__name__ == "HybridStorage"

        # Clean up
        os.environ.pop('MCP_USE_V2_STORAGE', None)

    def test_factory_handles_false_value(self):
        """Test that factory creates v1 storage when explicitly false."""
        os.environ['MCP_USE_V2_STORAGE'] = 'false'

        storage = create_storage(":memory:")
        assert type(storage).__name__ == "Storage"

        # Clean up
        os.environ.pop('MCP_USE_V2_STORAGE', None)


class TestDataMigration:
    """Test data migration from v1 to v2."""

    def test_v2_reads_v1_data(self):
        """Test that v2 storage can read data created by v1 storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Create data with v1
            v1_storage = Storage(db_path)
            v1_storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
            v1_storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")
            v1_storage.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")

            entry_count_v1 = v1_storage.count_entries()

            # Read same data with v2
            v2_storage = HybridStorage(db_path)

            # Verify v2 can read all v1 data
            assert v2_storage.is_domain_blacklisted("evil.com") is True
            assert v2_storage.is_url_blacklisted("http://phishing.com/login") is True
            assert v2_storage.is_ip_blacklisted("192.168.1.100") is True
            assert v2_storage.count_entries() == entry_count_v1

    def test_v1_reads_v2_data(self):
        """Test that v1 storage can read data created by v2 storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Create data with v2
            v2_storage = HybridStorage(db_path)
            v2_storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
            v2_storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")
            v2_storage.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")

            entry_count_v2 = v2_storage.count_entries()

            # Read same data with v1
            v1_storage = Storage(db_path)

            # Verify v1 can read all v2 data
            assert v1_storage.is_domain_blacklisted("evil.com") is True
            assert v1_storage.is_url_blacklisted("http://phishing.com/login") is True
            assert v1_storage.is_ip_blacklisted("192.168.1.100") is True
            assert v1_storage.count_entries() == entry_count_v2


class TestAPICompatibility:
    """Test that v1 and v2 have compatible APIs."""

    def test_same_methods_available(self):
        """Test that v2 has all methods that v1 has."""
        v1 = Storage(":memory:")
        v2 = HybridStorage(":memory:")

        # Core lookup methods
        assert hasattr(v2, 'is_domain_blacklisted')
        assert hasattr(v2, 'is_url_blacklisted')
        assert hasattr(v2, 'is_ip_blacklisted')

        # Write methods
        assert hasattr(v2, 'add_domain')
        assert hasattr(v2, 'add_url')
        assert hasattr(v2, 'add_ip')
        assert hasattr(v2, 'add_domains')
        assert hasattr(v2, 'add_urls')
        assert hasattr(v2, 'add_ips')
        assert hasattr(v2, 'add_entries')

        # Statistics methods
        assert hasattr(v2, 'count_entries')
        assert hasattr(v2, 'get_source_counts')
        assert hasattr(v2, 'get_active_sources')
        assert hasattr(v2, 'sample_entries')

        # Utility methods
        assert hasattr(v2, 'flush_cache')
        assert hasattr(v2, 'remove_entry')
        assert hasattr(v2, 'log_update')
        assert hasattr(v2, 'get_last_update')
        assert hasattr(v2, 'get_last_update_per_source')
        assert hasattr(v2, 'get_update_history')
        assert hasattr(v2, 'get_source_type_counts')

    def test_same_method_signatures(self):
        """Test that methods have compatible signatures."""
        v1 = Storage(":memory:")
        v2 = HybridStorage(":memory:")

        # Add domain
        v1.add_domain("evil1.com", "2025-01-01", 9.0, "test")
        v2.add_domain("evil2.com", "2025-01-01", 9.0, "test")

        # Check domain
        assert v1.is_domain_blacklisted("evil1.com") is True
        assert v2.is_domain_blacklisted("evil2.com") is True

        # Get source
        assert v1.get_domain_blacklist_source("evil1.com") == "test"
        assert v2.get_domain_blacklist_source("evil2.com") == "test"


class TestDataConsistency:
    """Test data consistency between v1 and v2."""

    def test_domain_lookups_consistent(self):
        """Test that domain lookups produce same results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Create identical data
            v1 = Storage(db_path)
            v1.add_domain("evil.com", "2025-01-01", 9.0, "test")
            v1.add_domain("malware.org", "2025-01-01", 8.5, "test")

            v2 = HybridStorage(db_path)  # Loads same data

            # Test same domains
            test_domains = [
                "evil.com",
                "sub.evil.com",
                "malware.org",
                "safe.com",
            ]

            for domain in test_domains:
                v1_result = v1.is_domain_blacklisted(domain)
                v2_result = v2.is_domain_blacklisted(domain)
                assert v1_result == v2_result, f"Mismatch for {domain}: v1={v1_result}, v2={v2_result}"

    def test_url_lookups_consistent(self):
        """Test that URL lookups produce same results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            v1 = Storage(db_path)
            v1.add_url("http://phishing.com/login", "2025-01-01", 9.0, "test")

            v2 = HybridStorage(db_path)

            test_urls = [
                "http://phishing.com/login",
                "http://phishing.com/different",
                "http://safe.com",
            ]

            for url in test_urls:
                v1_result = v1.is_url_blacklisted(url)
                v2_result = v2.is_url_blacklisted(url)
                assert v1_result == v2_result, f"Mismatch for {url}"

    def test_ip_lookups_consistent(self):
        """Test that IP lookups produce same results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            v1 = Storage(db_path)
            v1.add_ip("192.168.1.100", "2025-01-01", 7.0, "test")
            v1.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")

            v2 = HybridStorage(db_path)

            test_ips = [
                "192.168.1.100",
                "192.168.1.101",
                "10.5.5.5",  # In CIDR range
                "203.0.113.1",  # Not blacklisted
            ]

            for ip in test_ips:
                v1_result = v1.is_ip_blacklisted(ip)
                v2_result = v2.is_ip_blacklisted(ip)
                assert v1_result == v2_result, f"Mismatch for {ip}"


class TestSwitchingBetweenVersions:
    """Test switching between v1 and v2 using environment variable."""

    def test_switching_with_env_var(self):
        """Test switching storage versions via environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Use v1
            os.environ.pop('MCP_USE_V2_STORAGE', None)
            storage1 = create_storage(db_path)
            storage1.add_domain("evil.com", "2025-01-01", 9.0, "test")
            assert type(storage1).__name__ == "Storage"

            # Switch to v2
            os.environ['MCP_USE_V2_STORAGE'] = 'true'
            storage2 = create_storage(db_path)
            assert type(storage2).__name__ == "HybridStorage"
            assert storage2.is_domain_blacklisted("evil.com") is True

            # Switch back to v1
            os.environ['MCP_USE_V2_STORAGE'] = 'false'
            storage3 = create_storage(db_path)
            assert type(storage3).__name__ == "Storage"
            assert storage3.is_domain_blacklisted("evil.com") is True

            # Clean up
            os.environ.pop('MCP_USE_V2_STORAGE', None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
