import os
import sqlite3
import subprocess
import sys
import threading

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from agents_runner.gh.polling_state import PollingStateStore


def _store(tmp_path: Path, *, memory_only: bool = False) -> PollingStateStore:
    return PollingStateStore(
        database_path=str(tmp_path / "state.sqlite3"),
        key_path=str(tmp_path / "state.key"),
        lock_path=str(tmp_path / "state.lock"),
        memory_only=memory_only,
    )


def test_observation_upsert_and_encrypted_persistence(tmp_path):
    first = _store(tmp_path)
    first.record_observation(
        repo="org/repo", item_type="issue", number=3, activity_iso="2025-01-01T00:00:00Z", now_epoch=10
    )
    first.record_observation(
        repo="org/repo", item_type="issue", number=3, activity_iso="2025-01-02T00:00:00+00:00", now_epoch=20
    )
    second = _store(tmp_path)
    row = second.get_observation(repo="org/repo", item_type="issue", number=3)
    assert row is not None
    assert row.first_seen_epoch == 10
    assert row.last_activity_epoch == 1735776000
    assert row.last_activity_iso == "2025-01-02T00:00:00+00:00"


def test_concurrent_threads(tmp_path):
    store = _store(tmp_path)
    errors = []

    def worker(index: int) -> None:
        try:
            store.record_observation(
                repo="o/r", item_type="issue", number=1, activity_iso="2025-01-01T00:00:00Z", now_epoch=index
            )
            store.reserve_mention(
                emit_key=f"emit-{index}",
                mention_key=f"m-{index}",
                repo="o/r",
                item_type="issue",
                number=1,
                now_epoch=index,
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert len(store.list_processed_mentions()) == 8
    assert store.get_observation(repo="o/r", item_type="issue", number=1) is not None


def test_cross_process_initialization(tmp_path):
    script = "from agents_runner.gh.polling_state import PollingStateStore; import sys; s=PollingStateStore(database_path=sys.argv[1],key_path=sys.argv[2],lock_path=sys.argv[3]); s.reserve_mention(emit_key='x',mention_key='m',repo='o/r',item_type='issue',number=1,now_epoch=1)"
    paths = [str(tmp_path / name) for name in ("state.sqlite3", "state.key", "state.lock")]
    processes = [subprocess.Popen([sys.executable, "-c", script, *paths]) for _ in range(2)]
    assert [process.wait(timeout=15) for process in processes] == [0, 0]
    assert len(_store(tmp_path).list_processed_mentions()) == 1


def test_missing_key_is_private_and_sentinel_exists(tmp_path):
    _store(tmp_path)
    assert (tmp_path / "state.key").stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(tmp_path / "state.sqlite3") as db:
        assert db.execute("SELECT value FROM meta WHERE key='key_sentinel'").fetchone()[0]


def test_corrupt_key_quarantines_database(tmp_path):
    original = _store(tmp_path)
    original.record_observation(repo="o/r", item_type="issue", number=1, activity_iso="bad", now_epoch=1)
    (tmp_path / "state.key").write_bytes(b"garbage")
    recovered = _store(tmp_path)
    assert recovered.get_observation(repo="o/r", item_type="issue", number=1) is None
    assert list(tmp_path.glob("state.key.invalid-*"))
    assert list(tmp_path.glob("state.sqlite3.corrupt-*"))


def test_corrupt_database_is_quarantined(tmp_path):
    (tmp_path / "state.sqlite3").write_bytes(b"not a database")
    store = _store(tmp_path)
    assert list(tmp_path.glob("state.sqlite3.corrupt-*"))
    assert store.reserve_mention(emit_key="e", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=1)


def test_busy_database_is_not_quarantined(tmp_path):
    store = _store(tmp_path)
    store.reserve_mention(emit_key="e", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=1)
    blocker = sqlite3.connect(tmp_path / "state.sqlite3", timeout=0.1, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            store.reserve_mention(
                emit_key="other", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=2
            )
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    assert store.is_mention_processed("e")
    assert not list(tmp_path.glob("state.sqlite3.corrupt-*"))


def test_memory_only_round_trip(tmp_path):
    store = _store(tmp_path, memory_only=True)
    assert store.reserve_mention(emit_key="e", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=1)
    assert len(store.list_processed_mentions()) == 1
    assert not list(tmp_path.iterdir())


def test_sentinel_mismatch_recovers(tmp_path):
    store = _store(tmp_path)
    store.reserve_mention(emit_key="e", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=1)
    (tmp_path / "state.key").unlink()
    (tmp_path / "state.key").write_bytes(Fernet.generate_key())
    recovered = _store(tmp_path)
    assert recovered.list_processed_mentions() == []
    assert list(tmp_path.glob("state.sqlite3.corrupt-*"))


def test_reservation_lifecycle_and_stale_release(tmp_path):
    store = _store(tmp_path)
    assert store.reserve_mention(emit_key="a", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=1)
    assert not store.reserve_mention(
        emit_key="a", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=2
    )
    assert store.is_mention_processed("a")
    store.reserve_mention(emit_key="b", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=100)
    assert store.ack_item_mentions(repo="o/r", item_type="issue", number=1, now_epoch=101) == 2
    store.reserve_mention(emit_key="c", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=160)
    store.reserve_mention(emit_key="d", mention_key="n", repo="o/r", item_type="issue", number=2, now_epoch=100)
    assert store.release_stale_reservations(now_epoch=200, ttl_s=50) == 1


def test_prune_pending_anchor_and_policy_round_trips(tmp_path):
    store = _store(tmp_path)
    for number, epoch in ((1, 1), (2, 90000)):
        store.record_observation(repo="o/r", item_type="issue", number=number, activity_iso="invalid", now_epoch=epoch)
    assert store.prune_observations(now_epoch=100000, retention_days=1) == 1
    assert store.get_observation(repo="o/r", item_type="issue", number=2) is not None
    store.set_pending_anchor(mention_key="m", repo="o/r", item_type="issue", number=2, now_epoch=4)
    assert store.list_pending_anchors()[0].blocked_since_epoch == 4
    store.remove_pending_anchor("m")
    assert store.list_pending_anchors() == []
    store.set_policy_fingerprint(env_id="env", repo="o/r", fingerprint="fp", now_epoch=5)
    assert store.get_policy_fingerprint(env_id="env", repo="o/r") == "fp"


def test_wal_quarantine_while_old_store_open(tmp_path):
    old = _store(tmp_path)
    old.reserve_mention(emit_key="e", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=1)
    with open(tmp_path / "state.sqlite3", "wb") as stream:
        stream.write(b"corrupt")
    fresh = _store(tmp_path)
    assert fresh.reserve_mention(
        emit_key="fresh", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=2
    )
    assert fresh.is_mention_processed("fresh")


def test_unwritable_path_fails_cleanly_or_memory_store_works(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can write chmod-000 directories")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0)
    try:
        with pytest.raises(OSError):
            PollingStateStore(
                database_path=str(blocked / "db"), key_path=str(blocked / "key"), lock_path=str(blocked / "lock")
            )
    finally:
        blocked.chmod(0o700)
    store = _store(tmp_path, memory_only=True)
    assert store.reserve_mention(emit_key="e", mention_key="m", repo="o/r", item_type="issue", number=1, now_epoch=1)
    assert len(store.list_processed_mentions()) == 1
