"""Shared storage contract suite.

Every test is parametrized over both storage backends — the legacy
``sec_mcp.storage.Storage`` (v1, SQLite-only) and
``sec_mcp.storage_v2.HybridStorage`` (v2, in-memory + SQLite) — so the
behaviors the contract covers must hold identically for each: history
filters, CIDR source attribution, and removal-then-lookup.

``pytest -k contract`` selects this whole file.
"""

import pytest

from sec_mcp.storage import Storage
from sec_mcp.storage_base import StorageProtocol
from sec_mcp.storage_v2 import HybridStorage


# Backends under contract: a fresh file-backed store per test. HybridStorage
# rejects ":memory:" by design (each connection would see a different empty
# database), so both backends run against real files here.
@pytest.fixture(params=[Storage, HybridStorage], ids=["v1-sqlite", "v2-hybrid"])
def storage(request, tmp_path):
    return request.param(str(tmp_path / "contract.db"))


class TestStorageProtocolConformance:
    """Both backends implement the one StorageProtocol surface."""

    def test_contract_isinstance_storage_protocol(self, storage):
        assert isinstance(storage, StorageProtocol)

    def test_contract_shared_method_surface(self, storage):
        for method in (
            "is_domain_blacklisted",
            "is_url_blacklisted",
            "is_ip_blacklisted",
            "get_domain_blacklist_source",
            "get_url_blacklist_source",
            "get_ip_blacklist_source",
            "add_domain",
            "add_url",
            "add_ip",
            "add_domains",
            "add_urls",
            "add_ips",
            "add_entries",
            "remove_entry",
            "count_entries",
            "get_source_counts",
            "get_source_type_counts",
            "get_active_sources",
            "sample_entries",
            "get_last_update",
            "get_last_update_per_source",
            "get_update_history",
            "log_update",
            "flush_cache",
        ):
            assert callable(getattr(storage, method, None)), method


class TestContractLookups:
    """Lookup and source-attribution parity."""

    def test_contract_domain_lookup_and_source(self, storage):
        storage.add_domain("evil.com", "2025-01-01", 9.0, "PhishTank")

        assert storage.is_domain_blacklisted("evil.com") is True
        assert storage.is_domain_blacklisted("sub.evil.com") is True
        assert storage.is_domain_blacklisted("safe.com") is False

        assert storage.get_domain_blacklist_source("evil.com") == "PhishTank"
        assert storage.get_domain_blacklist_source("sub.evil.com") == "PhishTank"
        assert storage.get_domain_blacklist_source("safe.com") is None

    def test_contract_url_lookup_and_source(self, storage):
        storage.add_url("http://phishing.example.com/login", "2025-01-01", 8.5, "URLhaus")

        assert storage.is_url_blacklisted("http://phishing.example.com/login") is True
        assert storage.is_url_blacklisted("http://phishing.example.com/other") is False

        assert (
            storage.get_url_blacklist_source("http://phishing.example.com/login") == "URLhaus"
        )
        assert storage.get_url_blacklist_source("http://safe.example.com") is None

    def test_contract_exact_ip_lookup_and_source(self, storage):
        storage.add_ip("203.0.113.42", "2025-01-01", 7.0, "BlocklistDE")
        storage.add_ip("2001:db8::1", "2025-01-01", 7.0, "BlocklistDE")

        assert storage.is_ip_blacklisted("203.0.113.42") is True
        assert storage.is_ip_blacklisted("203.0.113.43") is False
        assert storage.is_ip_blacklisted("2001:db8::1") is True
        assert storage.is_ip_blacklisted("2001:db8::2") is False

        assert storage.get_ip_blacklist_source("203.0.113.42") == "BlocklistDE"
        assert storage.get_ip_blacklist_source("203.0.113.43") is None

    def test_contract_cidr_source_attribution(self, storage):
        """An IP inside a blacklisted CIDR attributes that range's source."""
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "SpamhausDROP")

        assert storage.is_ip_blacklisted("10.1.2.3") is True
        assert storage.is_ip_blacklisted("10.255.255.255") is True
        assert storage.is_ip_blacklisted("11.0.0.1") is False

        # The finding: is_ip_blacklisted agreed the member IP was bad, but
        # get_ip_blacklist_source could not say who blacklisted it.
        assert storage.get_ip_blacklist_source("10.1.2.3") == "SpamhausDROP"
        assert storage.get_ip_blacklist_source("11.0.0.1") is None


class TestContractUpdateHistory:
    """Update-history filters must work identically on both backends."""

    def test_contract_update_history_unfiltered(self, storage):
        storage.log_update("OpenPhish", 100)
        storage.log_update("PhishTank", 200)

        history = storage.get_update_history()
        assert len(history) == 2
        assert history[0]["source"] == "OpenPhish"
        assert history[0]["entry_count"] == 100
        assert history[1]["source"] == "PhishTank"

    def test_contract_update_history_filter_source(self, storage):
        storage.log_update("OpenPhish", 100)
        storage.log_update("PhishTank", 200)
        storage.log_update("OpenPhish", 150)

        history = storage.get_update_history(source="OpenPhish")
        assert len(history) == 2
        assert all(h["source"] == "OpenPhish" for h in history)

        history = storage.get_update_history(source="NoSuchSource")
        assert history == []

    def test_contract_update_history_filter_range(self, storage):
        storage.log_update("OpenPhish", 100)

        # Wide-open range includes the row.
        history = storage.get_update_history(start="1970-01-01", end="2999-01-01")
        assert len(history) == 1

        # A start in the far future excludes it; an end in the past does too.
        assert storage.get_update_history(start="2999-01-01") == []
        assert storage.get_update_history(end="1970-01-01") == []

    def test_contract_update_history_empty(self, storage):
        assert storage.get_update_history() == []


class TestContractRemovalThenLookup:
    """remove_entry must really un-blacklist: lookup and attribution both go negative."""

    def test_contract_remove_domain_then_lookup(self, storage):
        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
        assert storage.is_domain_blacklisted("evil.com") is True

        assert storage.remove_entry("evil.com") is True
        assert storage.is_domain_blacklisted("evil.com") is False
        assert storage.get_domain_blacklist_source("evil.com") is None

    def test_contract_remove_url_then_lookup(self, storage):
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")
        assert storage.is_url_blacklisted("http://phishing.com/login") is True

        assert storage.remove_entry("http://phishing.com/login") is True
        assert storage.is_url_blacklisted("http://phishing.com/login") is False
        assert storage.get_url_blacklist_source("http://phishing.com/login") is None

    def test_contract_remove_ip_then_lookup(self, storage):
        storage.add_ip("192.0.2.100", "2025-01-01", 7.0, "test")
        assert storage.is_ip_blacklisted("192.0.2.100") is True

        assert storage.remove_entry("192.0.2.100") is True
        assert storage.is_ip_blacklisted("192.0.2.100") is False
        assert storage.get_ip_blacklist_source("192.0.2.100") is None

    def test_contract_remove_cidr_then_lookup(self, storage):
        """Removing a CIDR frees its member IPs on both backends."""
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")

        # Populate any positive cache/matcher state before removal.
        assert storage.is_ip_blacklisted("10.1.2.3") is True
        assert storage.get_ip_blacklist_source("10.1.2.3") == "test"

        assert storage.remove_entry("10.0.0.0/8") is True
        assert storage.is_ip_blacklisted("10.1.2.3") is False
        assert storage.get_ip_blacklist_source("10.1.2.3") is None

    def test_contract_remove_missing_entry_returns_false(self, storage):
        assert storage.remove_entry("never-added.example.com") is False


class TestContractCounting:
    """Entry and per-source counts must not double-count on either backend."""

    def test_contract_count_entries(self, storage):
        storage.add_domain("evil.com", "2025-01-01", 9.0, "test")
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "test")
        storage.add_ip("192.0.2.100", "2025-01-01", 7.0, "test")
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "test")

        assert storage.count_entries() == 4

    def test_contract_source_counts(self, storage):
        storage.add_domain("evil1.com", "2025-01-01", 9.0, "Source1")
        storage.add_domain("evil2.com", "2025-01-01", 9.0, "Source1")
        storage.add_url("http://phishing.com/login", "2025-01-01", 8.5, "Source2")
        storage.add_ip("192.0.2.100", "2025-01-01", 7.0, "Source1")

        counts = storage.get_source_counts()
        assert counts["Source1"] == 3  # 2 domains + 1 IP — counted once
        assert counts["Source2"] == 1

    def test_contract_active_sources(self, storage):
        storage.add_domain("evil.com", "2025-01-01", 9.0, "OpenPhish")
        storage.add_ip("10.0.0.0/8", "2025-01-01", 8.0, "SpamhausDROP")

        sources = storage.get_active_sources()
        assert sorted(sources) == ["OpenPhish", "SpamhausDROP"]


class TestContractBatchWrites:
    """Batch add APIs behave like the single-entry ones."""

    def test_contract_batch_add(self, storage):
        storage.add_domains([("evil1.com", "2025-01-01", 9.0, "test")])
        storage.add_urls([("http://phishing.com/x", "2025-01-01", 8.5, "test")])
        storage.add_ips(
            [("192.0.2.1", "2025-01-01", 7.0, "test"), ("172.16.0.0/12", "2025-01-01", 8.0, "test")]
        )

        assert storage.is_domain_blacklisted("evil1.com") is True
        assert storage.is_url_blacklisted("http://phishing.com/x") is True
        assert storage.is_ip_blacklisted("192.0.2.1") is True
        assert storage.is_ip_blacklisted("172.16.5.5") is True
        assert storage.count_entries() == 4
