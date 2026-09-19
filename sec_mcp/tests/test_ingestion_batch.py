"""Issue #56: feed ingestion writes each feed in batches, not per row.

One ``BlacklistUpdater._update_source`` call must land the whole feed
through ``executemany`` — at most 3 calls per source (one per entry-type
bucket: domains, URLs, IPs) — and must never open a ``sqlite3.connect``
inside a per-row loop. The spy replaces ``sqlite3.connect`` so both
storage backends are measured on the real update path:
``_update_source`` → ``storage.add_entries`` → SQLite writes.
"""

import sqlite3
from unittest.mock import MagicMock

import pytest

from sec_mcp.storage import Storage
from sec_mcp.storage_v2 import HybridStorage
from sec_mcp.update_blacklist import BlacklistUpdater

_REAL_CONNECT = sqlite3.connect


class _FakeStreamResponse:
    """Minimal async byte-streaming response (see test_update_blacklist)."""

    def __init__(self, chunks):
        self._chunks = chunks

    def raise_for_status(self):
        pass

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _stream_client(chunks):
    client = MagicMock()
    client.stream = MagicMock(return_value=_FakeStreamCM(_FakeStreamResponse(chunks)))
    return client


class _RecordingConnection:
    """Delegating wrapper that counts batch calls on a real connection.

    ``sqlite3.Connection`` is a C extension type whose methods cannot be
    patched, so the spy wraps each connection ``sqlite3.connect`` returns
    and counts ``executemany``/``execute`` on the proxy instead.
    """

    def __init__(self, real_conn, recorder):
        self._real_conn = real_conn
        self._recorder = recorder

    def executemany(self, *args, **kwargs):
        self._recorder.executemany_calls += 1
        return self._real_conn.executemany(*args, **kwargs)

    def execute(self, *args, **kwargs):
        self._recorder.execute_calls += 1
        return self._real_conn.execute(*args, **kwargs)

    def __enter__(self):
        self._real_conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._real_conn.__exit__(exc_type, exc, tb)

    def __getattr__(self, name):
        return getattr(self._real_conn, name)


class _ConnectRecorder:
    """Spy standing in for ``sqlite3.connect`` during one feed update.

    Counts connections opened plus ``executemany``/``execute`` calls made
    on every connection it hands out, across both storage backends.
    """

    def __init__(self):
        self.connect_calls = 0
        self.executemany_calls = 0
        self.execute_calls = 0

    def __call__(self, *args, **kwargs):
        self.connect_calls += 1
        return _RecordingConnection(_REAL_CONNECT(*args, **kwargs), self)


# Nine feed rows spanning all three entry-type buckets (3 domains,
# 3 IPs, 3 path-bearing URLs) so every batch statement fires once.
_FEED = (
    b"bad-one.com\n"
    b"bad-two.net\n"
    b"phish-three.org\n"
    b"9.9.9.9\n"
    b"8.8.8.8\n"
    b"203.0.113.7\n"
    b"https://evil.example/path\n"
    b"http://mal.example/x\n"
    b"https://badsite.example/login\n"
)
_FEED_ROWS = 9

# Constant bounds proving no per-row database work. A per-row loop would
# cost at least one call per feed row (9 here), so any bound below that
# catches it:
# - v1 Storage: 1 connect for add_entries + 1 for log_update = 2
# - v2 HybridStorage: 1 connect per upsert bucket + log_update = 4
# - both: exactly 1 execute (log_update's INSERT) outside executemany
_MAX_CONNECTS = 5
_MAX_EXECUTE = 2


@pytest.fixture(params=[Storage, HybridStorage], ids=["v1-sqlite", "v2-hybrid"])
def storage(request, tmp_path):
    return request.param(str(tmp_path / "feed.db"))


@pytest.fixture
def recorder(monkeypatch):
    rec = _ConnectRecorder()
    monkeypatch.setattr(sqlite3, "connect", rec)
    return rec


@pytest.mark.asyncio
async def test_ingestion_batches_executemany_per_source(storage, recorder):
    """≤ 3 executemany calls per source — one per domain/url/ip bucket."""
    updater = BlacklistUpdater(storage)
    for source in ("TestFeedA", "TestFeedB"):
        before = recorder.executemany_calls
        await updater._update_source(
            _stream_client([_FEED]), source, f"https://feed.example/{source}.txt"
        )
        batch_calls = recorder.executemany_calls - before
        assert 1 <= batch_calls <= 3, (
            f"{source}: feed ingestion must batch via executemany "
            f"(≤3 calls per source), got {batch_calls}"
        )
    assert storage.count_entries() >= _FEED_ROWS


@pytest.mark.asyncio
async def test_ingestion_no_per_row_connect(storage, recorder):
    """0 sqlite3.connect calls inside a per-row loop.

    Connection count stays a small constant (v1: 2, v2: 4) while a
    per-row write loop would need at least one connect per feed row.
    """
    updater = BlacklistUpdater(storage)
    await updater._update_source(
        _stream_client([_FEED]), "TestFeed", "https://feed.example/list.txt"
    )
    assert recorder.connect_calls <= _MAX_CONNECTS, (
        f"ingestion opened {recorder.connect_calls} connections for a "
        f"{_FEED_ROWS}-row feed — connects must not scale with rows"
    )
    assert recorder.connect_calls < _FEED_ROWS


@pytest.mark.asyncio
async def test_ingestion_no_per_row_execute(storage, recorder):
    """Rows land via executemany, not per-row execute calls.

    Only ``log_update``'s single INSERT runs through execute; a per-row
    insert loop would execute at least once per feed row.
    """
    updater = BlacklistUpdater(storage)
    await updater._update_source(
        _stream_client([_FEED]), "TestFeed", "https://feed.example/list.txt"
    )
    assert recorder.execute_calls <= _MAX_EXECUTE, (
        f"ingestion ran {recorder.execute_calls} execute() calls for a "
        f"{_FEED_ROWS}-row feed — per-row inserts must use executemany"
    )
