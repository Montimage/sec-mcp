"""Tests for BlacklistUpdater's shared update scheduler."""

import json
from datetime import datetime, timedelta

import pytest

from sec_mcp.storage import Storage
from sec_mcp.update_blacklist import BlacklistUpdater


@pytest.fixture(autouse=True)
def _stop_scheduler_after_test():
    yield
    BlacklistUpdater.stop()


def _enable_scheduler(monkeypatch):
    monkeypatch.delenv("MCP_DISABLE_SCHEDULER", raising=False)


def test_scheduled_job_runs_update_with_fake_clock(tmp_path, monkeypatch):
    _enable_scheduler(monkeypatch)
    config = tmp_path / "sources.json"
    config.write_text(json.dumps({
        "blacklist_sources": {"TestFeed": "https://feed.example/list.txt"}
    }))
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "TestFeed.txt").write_text("1.2.3.4\n5.6.7.8\n")
    storage = Storage(str(tmp_path / "feed.db"))

    BlacklistUpdater(storage, config_path=str(config))
    job = BlacklistUpdater._scheduler.jobs[0]
    job.next_run = datetime.now() - timedelta(seconds=1)
    BlacklistUpdater._scheduler.run_pending()

    assert storage.is_ip_blacklisted("1.2.3.4")
    assert storage.is_ip_blacklisted("5.6.7.8")
    assert storage.get_last_update() != datetime.min


def test_two_updaters_register_one_job(tmp_path, monkeypatch):
    _enable_scheduler(monkeypatch)
    BlacklistUpdater(Storage(str(tmp_path / "a.db")))
    BlacklistUpdater(Storage(str(tmp_path / "b.db")))
    assert len(BlacklistUpdater._scheduler.jobs) == 1


def test_scheduler_stop_is_idempotent_and_joins_thread(tmp_path, monkeypatch):
    _enable_scheduler(monkeypatch)
    BlacklistUpdater(Storage(str(tmp_path / "s.db")))
    thread = BlacklistUpdater._scheduler_thread
    assert thread is not None and thread.is_alive()

    BlacklistUpdater.stop()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert BlacklistUpdater._scheduler is None
    assert BlacklistUpdater._scheduler_thread is None

    BlacklistUpdater.stop()
    BlacklistUpdater.stop()


def test_scheduler_respects_disable_env(tmp_path, monkeypatch):
    BlacklistUpdater(Storage(str(tmp_path / "d.db")))
    assert BlacklistUpdater._scheduler is None
    assert BlacklistUpdater._scheduler_thread is None
