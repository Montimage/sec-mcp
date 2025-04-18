"""Test the storage functionality."""
import pytest
import os
from sec_mcp.storage import Storage

@pytest.fixture
def storage():
    """Create a temporary test database."""
    db_path = "test_mcp.db"
    storage = Storage(db_path)
    yield storage
    # Cleanup after tests
    if os.path.exists(db_path):
        os.remove(db_path)

def test_add_and_check_entries(storage):
    """Test adding entries and checking if they're blacklisted."""
    entries = [
        ("https://test1.com", "1.1.1.1", "2025-04-18T00:00:00", 5.0),
        ("https://test2.com", "2.2.2.2", "2025-04-18T00:00:00", 7.5)
    ]
    storage.add_entries(entries)
    # URLs and IPs should be recognized as blacklisted
    assert storage.is_blacklisted("https://test1.com")
    assert storage.is_blacklisted("1.1.1.1")
    assert storage.is_blacklisted("https://test2.com")
    assert not storage.is_blacklisted("https://safe.com")

def test_entry_count(storage):
    """Test counting total entries."""
    entries = [
        ("https://test1.com", "1.1.1.1", "2025-04-18T00:00:00", 5.0),
        ("https://test2.com", "2.2.2.2", "2025-04-18T00:00:00", 7.5),
        ("https://test3.com", "3.3.3.3", "2025-04-18T00:00:00", 2.5)
    ]
    storage.add_entries(entries)
    assert storage.count_entries() == 3

def test_cache_functionality(storage):
    """Test that the in-memory cache works correctly."""
    entry = ("https://cached.com", "9.9.9.9", "2025-04-18T00:00:00", 8.0)
    storage.add_entries([entry])
    # First check should populate cache for URL and IP
    assert storage.is_blacklisted("https://cached.com")
    # Cache should contain both URL and IP
    with storage._cache_lock:
        assert "https://cached.com" in storage._cache
        assert "9.9.9.9" in storage._cache
