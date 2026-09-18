"""Tests for BlacklistUpdater's shared update scheduler."""

import json
import threading
from datetime import datetime, timedelta

import pytest
import schedule

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


def test_stop_blocks_ensure_until_transition_finishes(tmp_path, monkeypatch):
    _enable_scheduler(monkeypatch)
    updater = BlacklistUpdater(Storage(str(tmp_path / "r.db")))
    cls = BlacklistUpdater
    old_scheduler = cls._scheduler
    old_thread = cls._scheduler_thread

    mid_transition = threading.Event()
    release = threading.Event()
    ensure_done = threading.Event()
    ensure_errors = []

    original_join = old_thread.join

    def blocking_join(timeout=None):
        mid_transition.set()
        release.wait(timeout=10)
        return original_join(timeout=timeout)

    old_thread.join = blocking_join

    stop_thread = threading.Thread(target=cls.stop, daemon=True)
    stop_thread.start()
    assert mid_transition.wait(timeout=10)

    def run_ensure():
        try:
            updater._ensure_scheduler()
        except Exception as e:
            ensure_errors.append(e)
        finally:
            ensure_done.set()

    ensure_thread = threading.Thread(target=run_ensure, daemon=True)
    ensure_thread.start()
    # stop() still holds the lock mid-transition, so ensure must not complete.
    assert not ensure_done.wait(timeout=0.5)

    release.set()
    stop_thread.join(timeout=10)
    ensure_thread.join(timeout=10)

    assert not ensure_errors
    assert not old_thread.is_alive()
    assert cls._scheduler is not None and cls._scheduler is not old_scheduler
    assert len(cls._scheduler.jobs) == 1
    new_thread = cls._scheduler_thread
    assert new_thread is not None and new_thread is not old_thread
    assert new_thread.is_alive()
    assert cls._scheduler_stop is not None and not cls._scheduler_stop.is_set()

    cls.stop()
    assert not new_thread.is_alive()
    assert cls._scheduler_thread is None


def test_scheduler_respects_disable_env(tmp_path, monkeypatch):
    BlacklistUpdater(Storage(str(tmp_path / "d.db")))
    assert BlacklistUpdater._scheduler is None
    assert BlacklistUpdater._scheduler_thread is None


def test_scheduler_tick_contains_job_exception():
    scheduler = schedule.Scheduler()
    scheduler.every().second.do(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    scheduler.jobs[0].next_run = datetime.now() - timedelta(seconds=1)
    BlacklistUpdater._scheduler_tick(scheduler)
    scheduler.clear()

    ran = []
    scheduler.every().second.do(lambda: ran.append(True))
    scheduler.jobs[-1].next_run = datetime.now() - timedelta(seconds=1)
    BlacklistUpdater._scheduler_tick(scheduler)
    assert ran == [True]
