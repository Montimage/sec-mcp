"""Issue #50 — one URL normalization shared by both storage backends.

``sec_mcp.storage_base.normalize_url`` is the single canonicalization every
backend applies — on write, on lookup, and on the rows already stored in
``blacklist_url`` (``init_db`` rewrites non-canonical rows). These tests pin
the canonical forms and assert the v1 (SQLite exact-match) and v2 (in-memory
index) backends return the same verdict for a table of 20 URL variants.

``pytest -k normalization`` selects this whole file plus the legacy
normalization tests in ``test_compatibility.py``.
"""

import sqlite3

import pytest

from sec_mcp import storage, storage_base, storage_v2
from sec_mcp.storage import Storage
from sec_mcp.storage_v2 import HybridStorage


class TestSingleNormalizeUrl:
    """There is exactly one normalize_url implementation."""

    def test_normalization_single_home(self):
        """Both backends resolve the same function object."""
        assert storage_v2.normalize_url is storage_base.normalize_url
        assert storage.storage_base.normalize_url is storage_base.normalize_url

    def test_normalization_canonical_forms(self):
        """Canonical forms: lowercase, http default, no tracking, no trailing slash."""
        normalize_url = storage_base.normalize_url

        assert normalize_url("HTTP://EVIL.COM/") == "http://evil.com"
        assert normalize_url("http://evil.com") == "http://evil.com"
        assert normalize_url("http://evil.com/") == "http://evil.com"
        assert normalize_url("http://evil.com/path/") == "http://evil.com/path"
        assert normalize_url("http://evil.com/?utm_source=spam") == "http://evil.com"
        assert normalize_url("http://evil.com/?fbclid=123") == "http://evil.com"
        assert (
            normalize_url("http://evil.com/page?utm_medium=email&valid=1")
            == "http://evil.com/page?valid=1"
        )
        # Non-tracking query params survive.
        assert normalize_url("http://evil.com/x?keep=1") == "http://evil.com/x?keep=1"
        # Fragments are dropped, schemes and ports preserved.
        assert normalize_url("http://evil.com/x#frag") == "http://evil.com/x"
        assert normalize_url("https://evil.com:8443/x") == "https://evil.com:8443/x"
        # Bare hosts and scheme-relative URLs get the default http scheme.
        assert normalize_url("evil.com/path") == "http://evil.com/path"
        assert normalize_url("//evil.com/path") == "http://evil.com/path"

    def test_normalization_idempotent(self):
        """Normalizing twice must not change the result."""
        normalize_url = storage_base.normalize_url
        for url in (
            "HTTP://EVIL.COM/",
            "http://evil.com/path/?utm_source=x&keep=1",
            "evil.com",
            "//evil.com/x",
            "https://evil.com:8443/x#f",
        ):
            assert normalize_url(normalize_url(url)) == normalize_url(url)


class TestNormalizationVerdictParity:
    """Both backends return the same verdict for a table of 20 URL variants."""

    # Entries seeded through the v1 write path (which stores canonical forms).
    SEED_URLS = (
        "http://evil.com/steal",
        "http://phish.net",
        "https://bad.org/path/?utm_source=tracker",  # stored as https://bad.org/path
    )

    # (query, expected verdict) — expectations follow the canonical forms
    # pinned by TestSingleNormalizeUrl.
    VARIANTS = (
        ("http://evil.com/steal", True),                    # exact
        ("HTTP://EVIL.COM/STEAL", True),                    # case
        ("http://evil.com/steal/", True),                   # trailing slash
        ("http://evil.com/steal?utm_source=spam", True),    # tracking param
        ("http://evil.com/steal?keep=1&utm_medium=e", False),  # real param differs
        ("http://evil.com/other", False),                   # different path
        ("https://evil.com/steal", False),                  # scheme differs
        ("//evil.com/steal", True),                         # scheme-relative
        ("http://phish.net", True),                         # exact, root
        ("http://phish.net/", True),                        # root slash
        ("HTTP://PHISH.NET/?fbclid=9", True),               # case + tracking
        ("phish.net", True),                                # bare host
        ("https://phish.net", False),                       # scheme differs
        ("https://bad.org/path", True),                     # stored canonical
        ("https://bad.org/path/", True),                    # trailing slash
        ("HTTPS://BAD.ORG/PATH/?utm_medium=e", True),       # case + tracking
        ("https://bad.org/path?keep=1", False),             # real param differs
        ("http://bad.org/path", False),                     # scheme differs
        ("http://safe.com/", False),                        # not blacklisted
        ("http://evil.com", False),                         # host only
    )

    def test_normalization_variant_table_has_20_rows(self):
        assert len(self.VARIANTS) == 20

    def test_normalization_verdicts_agree_on_20_variants(self, tmp_path):
        db_path = str(tmp_path / "parity.db")

        v1 = Storage(db_path)
        for url in self.SEED_URLS:
            v1.add_url(url, "2025-01-01", 9.0, "test")

        v2 = HybridStorage(db_path)  # loads the same table

        for query, expected in self.VARIANTS:
            v1_verdict = v1.is_url_blacklisted(query)
            v2_verdict = v2.is_url_blacklisted(query)
            assert v1_verdict == expected, f"v1 verdict wrong for {query!r}"
            assert v2_verdict == expected, f"v2 verdict wrong for {query!r}"
            assert v1_verdict == v2_verdict, f"backends disagree on {query!r}"

    def test_normalization_source_attribution_agrees(self, tmp_path):
        db_path = str(tmp_path / "source.db")

        v1 = Storage(db_path)
        v1.add_url("http://evil.com/steal", "2025-01-01", 9.0, "PhishTank")
        v2 = HybridStorage(db_path)

        for query in (
            "http://evil.com/steal",
            "HTTP://EVIL.COM/STEAL/",
            "http://evil.com/steal?utm_source=spam",
        ):
            assert v1.get_url_blacklist_source(query) == "PhishTank"
            assert v2.get_url_blacklist_source(query) == "PhishTank"

    def test_normalization_remove_entry_agrees(self, tmp_path):
        """A variant-form removal un-blacklists on both backends."""
        db_path = str(tmp_path / "remove.db")

        v1 = Storage(db_path)
        v1.add_url("http://evil.com/steal", "2025-01-01", 9.0, "test")
        v2 = HybridStorage(db_path)

        assert v2.remove_entry("HTTP://EVIL.COM/STEAL/?utm_source=x") is True
        assert v2.is_url_blacklisted("http://evil.com/steal") is False
        assert v1.is_url_blacklisted("http://evil.com/steal") is False


class TestNormalizationLegacyRows:
    """Rows stored before normalization (or inserted directly) are canonicalized."""

    def test_normalization_canonicalizes_existing_table(self, tmp_path):
        db_path = str(tmp_path / "legacy.db")

        # Seed a raw variant row directly, bypassing the write path — the
        # state a pre-normalization database is in.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE blacklist_url (url TEXT PRIMARY KEY, date TEXT, score REAL, source TEXT)"
        )
        conn.execute(
            "INSERT INTO blacklist_url VALUES (?, ?, ?, ?)",
            ("HTTP://SEEDED.COM/PATH/?utm_source=x", "2025-01-01", 9.0, "test"),
        )
        conn.commit()
        conn.close()

        # Construction canonicalizes the table (init_db), so both backends
        # agree on every variant of the stored entry.
        v1 = Storage(db_path)
        v2 = HybridStorage(db_path)

        for query in (
            "http://seeded.com/path",
            "HTTP://SEEDED.COM/PATH/",
            "http://seeded.com/path?utm_source=x",
        ):
            assert v1.is_url_blacklisted(query) is True
            assert v2.is_url_blacklisted(query) is True

        # The table itself holds the canonical form now.
        rows = sqlite3.connect(db_path).execute(
            "SELECT url FROM blacklist_url"
        ).fetchall()
        assert rows == [("http://seeded.com/path",)]

    def test_normalization_colliding_variants_merge(self, tmp_path):
        """Rows that normalize to the same key collapse to one canonical row."""
        db_path = str(tmp_path / "merge.db")

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE blacklist_url (url TEXT PRIMARY KEY, date TEXT, score REAL, source TEXT)"
        )
        conn.executemany(
            "INSERT INTO blacklist_url VALUES (?, ?, ?, ?)",
            [
                ("HTTP://SEEDED.COM/PATH/", "2025-01-01", 9.0, "test"),
                ("http://seeded.com/path", "2025-01-02", 8.0, "test"),
            ],
        )
        conn.commit()
        conn.close()

        Storage(db_path)

        rows = sqlite3.connect(db_path).execute("SELECT url FROM blacklist_url").fetchall()
        assert rows == [("http://seeded.com/path",)]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
