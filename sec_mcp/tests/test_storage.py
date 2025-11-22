"""Test the storage functionality."""
import os

import pytest

from sec_mcp.storage import Storage


@pytest.fixture
def storage():
    """Create a temporary test database for storage tests."""
    db_path = "test_storage_sec_mcp.db"  # Using a more specific name for these tests
    # Ensure the directory for the test DB exists if it's not in the current dir
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    storage_instance = Storage(db_path=db_path)
    yield storage_instance
    # Cleanup after tests
    if os.path.exists(db_path):
        try:
            # Close connection if possible before removing, to avoid issues on some OS
            if hasattr(storage_instance, "conn") and storage_instance.conn:
                storage_instance.conn.close()
        except Exception:
            pass  # Ignore errors during cleanup
        os.remove(db_path)


def test_add_and_check_entries(storage):
    """Test adding entries and checking if they're blacklisted."""
    # Assuming add_url also implies adding the domain if it's a domain-only entry
    # and add_ip adds the IP. The source is 'TestSource' for these manual additions.
    storage.add_url("https://test1.com/path", "2025-04-18T00:00:00", 5.0, "TestSource")
    storage.add_ip("1.1.1.1", "2025-04-18T00:00:00", 5.0, "TestSource")
    storage.add_domain("test2.com", "2025-04-18T00:00:00", 7.5, "TestSource")

    assert storage.is_url_blacklisted("https://test1.com/path")
    assert storage.is_ip_blacklisted("1.1.1.1")
    assert storage.is_domain_blacklisted("test2.com")
    assert not storage.is_url_blacklisted("https://safe.com")
    assert not storage.is_domain_blacklisted("safe.com")
    assert not storage.is_ip_blacklisted("3.3.3.3")


def test_entry_count(storage):
    """Test counting total entries."""
    storage.add_url("https://testcount1.com/path", "2025-04-18T00:00:00", 5.0, "TestSource")
    storage.add_domain("testcount2.com", "2025-04-18T00:00:00", 7.5, "TestSource")
    storage.add_ip("3.3.3.3", "2025-04-18T00:00:00", 2.5, "TestSource")

    # count_entries() sums counts from all three tables (urls, domains, ips)
    assert storage.count_entries() == 3


def test_cache_functionality(storage):
    """Test that the in-memory cache works correctly."""
    url_to_cache = "https://cached.com/specific"
    ip_to_cache = "9.9.9.9"
    domain_to_cache = "cacheddomain.com"

    storage.add_url(url_to_cache, "2025-04-18T00:00:00", 8.0, "TestSource")
    storage.add_ip(ip_to_cache, "2025-04-18T00:00:00", 8.0, "TestSource")
    storage.add_domain(domain_to_cache, "2025-04-18T00:00:00", 8.0, "TestSource")

    # First checks should populate cache
    assert storage.is_url_blacklisted(url_to_cache)
    assert storage.is_ip_blacklisted(ip_to_cache)
    assert storage.is_domain_blacklisted(domain_to_cache)

    # Cache should contain these entries
    with storage._cache_lock:
        assert url_to_cache in storage._cache
        assert ip_to_cache in storage._cache
        assert domain_to_cache in storage._cache
