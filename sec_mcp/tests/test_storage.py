"""Test the storage functionality."""
import pytest
import os
from sec_mcp.storage import Storage
from datetime import datetime, timedelta

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
        ("https://test1.com", "Source1"),
        ("https://test2.com", "Source2")
    ]
    storage.add_entries(entries)
    
    assert storage.is_blacklisted("https://test1.com")
    assert storage.is_blacklisted("https://test2.com")
    assert not storage.is_blacklisted("https://safe.com")

def test_get_blacklist_source(storage):
    """Test retrieving the source of a blacklisted entry."""
    storage.add_entries([("https://test.com", "TestSource")])
    assert storage.get_blacklist_source("https://test.com") == "TestSource"
    assert storage.get_blacklist_source("https://nonexistent.com") is None

def test_entry_count(storage):
    """Test counting total entries."""
    entries = [
        ("https://test1.com", "Source1"),
        ("https://test2.com", "Source2"),
        ("https://test3.com", "Source3")
    ]
    storage.add_entries(entries)
    assert storage.count_entries() == 3

def test_get_active_sources(storage):
    """Test retrieving active sources."""
    entries = [
        ("https://test1.com", "Source1"),
        ("https://test2.com", "Source2"),
        ("https://test3.com", "Source1")
    ]
    storage.add_entries(entries)
    sources = storage.get_active_sources()
    assert len(sources) == 2
    assert "Source1" in sources
    assert "Source2" in sources

def test_cache_functionality(storage):
    """Test that the in-memory cache works correctly."""
    # Add an entry
    storage.add_entries([("https://cached.com", "Source")])
    
    # First check should populate cache
    assert storage.is_blacklisted("https://cached.com")
    
    # Second check should use cache
    with storage._cache_lock:
        assert "https://cached.com" in storage._cache
