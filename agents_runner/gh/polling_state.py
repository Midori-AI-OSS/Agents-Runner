"""Encrypted persistent memory for GitHub polling.

Identifiers remain queryable in SQLite by necessity; no tokens or issue/comment
content are stored. Store operations belong on worker threads, not the Qt GUI
thread, because initialization may wait briefly for the cross-process lock.
"""

from __future__ import annotations

import errno
import os
import sqlite3
import threading
import time

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from midori_ai_logger import MidoriAiLogger

from agents_runner.persistence import default_state_path

logger = MidoriAiLogger(channel=None, name=__name__)
_SENTINEL = b"gh-polling-state-v1"
_SCHEMA_VERSION = "1"
_singleton_lock = threading.RLock()
_singleton: PollingStateStore | None = None
_warned: set[str] = set()


@dataclass(frozen=True)
class ObservationRecord:
    repo: str
    item_type: str
    number: int
    first_seen_epoch: float
    last_activity_epoch: float
    last_activity_iso: str


@dataclass(frozen=True)
class ProcessedMention:
    emit_key: str
    mention_key: str
    repo: str
    item_type: str
    number: int
    status: str
    recorded_epoch: float


@dataclass(frozen=True)
class PendingAnchor:
    mention_key: str
    repo: str
    item_type: str
    number: int
    blocked_since_epoch: float


def _encrypt(key: bytes, plaintext: bytes) -> str:
    return Fernet(key).encrypt(plaintext).decode("ascii")


def _decrypt(key: bytes, token: str) -> bytes:
    try:
        return Fernet(key).decrypt(token.encode("ascii"))
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise ValueError("polling state value could not be decrypted") from exc


def _warn_once(category: str, message: str) -> None:
    if category not in _warned:
        _warned.add(category)
        logger.warning(message)


def _float_token(key: bytes, value: str) -> float:
    return float(_decrypt(key, value).decode("ascii"))


def _token_float(key: bytes, value: float) -> str:
    return _encrypt(key, repr(value).encode("ascii"))


@contextmanager
def _process_lock(path: str) -> Generator[None]:
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            import fcntl
        except ImportError:
            yield
            return
        deadline = time.monotonic() + 5.0
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("polling state initialization lock timed out")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class PollingStateStore:
    def __init__(self, *, database_path: str, key_path: str, lock_path: str, memory_only: bool = False) -> None:
        self.database_path: str = database_path
        self.key_path: str = key_path
        self.lock_path: str = lock_path
        self.memory_only: bool = memory_only
        self._mutex: threading.RLock = threading.RLock()
        self._observations: dict[tuple[str, str, int], tuple[float, float, str, float]] = {}
        self._mentions: dict[str, ProcessedMention] = {}
        self._anchors: dict[str, PendingAnchor] = {}
        self._fingerprints: dict[tuple[str, str], str] = {}
        self._key: bytes = b""
        if not memory_only:
            self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _key_file(self) -> bytes:
        try:
            fd = os.open(self.key_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError:
            key = Fernet.generate_key()
            try:
                fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return self._key_file()
            with os.fdopen(fd, "wb") as stream:
                stream.write(key)
            return key
        except OSError as exc:
            if exc.errno != errno.ELOOP:
                raise
            self._replace_invalid_key()
            return self._key_file()
        try:
            if not os.path.isfile(self.key_path) or os.path.islink(self.key_path):
                raise ValueError("invalid key file")
            key = os.read(fd, 4096)
        finally:
            os.close(fd)
        try:
            Fernet(key)
            return key
        except (ValueError, TypeError):
            self._replace_invalid_key()
            return self._key_file()

    def _replace_invalid_key(self) -> None:
        try:
            os.rename(self.key_path, f"{self.key_path}.invalid-{int(time.time())}")
        except OSError as exc:
            raise ValueError("polling state key could not be replaced") from exc
        _warn_once("invalid-key", "polling state key was invalid; starting with a new key")

    def _quarantine(self) -> None:
        suffix = f".corrupt-{int(time.time())}"
        for path in (self.database_path, f"{self.database_path}-wal", f"{self.database_path}-shm"):
            try:
                os.rename(path, path + suffix)
            except OSError:
                pass

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observed_items(repo TEXT NOT NULL, item_type TEXT NOT NULL, number INTEGER NOT NULL, first_seen_epoch TEXT NOT NULL, last_activity_epoch TEXT NOT NULL, last_activity_iso TEXT NOT NULL, last_seen_epoch TEXT NOT NULL, PRIMARY KEY(repo, item_type, number));
            CREATE TABLE IF NOT EXISTS processed_mentions(emit_key TEXT PRIMARY KEY, mention_key TEXT NOT NULL, repo TEXT NOT NULL, item_type TEXT NOT NULL, number INTEGER NOT NULL, status TEXT NOT NULL, recorded_epoch TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pending_anchors(mention_key TEXT PRIMARY KEY, repo TEXT NOT NULL, item_type TEXT NOT NULL, number INTEGER NOT NULL, blocked_since_epoch TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS policy_fingerprints(env_id TEXT NOT NULL, repo TEXT NOT NULL, fingerprint TEXT NOT NULL, updated_epoch TEXT NOT NULL, PRIMARY KEY(env_id, repo));
        """)
        connection.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (_SCHEMA_VERSION,))
        connection.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('key_sentinel', ?)", (_encrypt(self._key, _SENTINEL),)
        )

    def _initialize(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.database_path)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(self.key_path)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_path)), exist_ok=True)
        with _process_lock(self.lock_path):
            self._key = self._key_file()
            connection: sqlite3.Connection | None = None
            try:
                connection = self._connect()
                connection.execute("PRAGMA journal_mode=WAL")
                result = connection.execute("PRAGMA quick_check").fetchone()
                if result is None or result[0] != "ok":
                    raise sqlite3.DatabaseError("integrity check failed")
                has_meta = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
                ).fetchone()
                sentinel = (
                    connection.execute("SELECT value FROM meta WHERE key='key_sentinel'").fetchone()
                    if has_meta
                    else None
                )
                if sentinel is not None and _decrypt(self._key, sentinel[0]) != _SENTINEL:
                    connection.close()
                    connection = None
                    self._quarantine()
                    _warn_once("sentinel", "polling state database recovered after key rotation")
                self._create_schema(connection) if connection is not None else None
            except ValueError:
                if connection is not None:
                    connection.close()
                    connection = None
                self._quarantine()
                _warn_once("sentinel", "polling state database recovered after key rotation")
            except sqlite3.DatabaseError as exc:
                if connection is not None:
                    connection.close()
                    connection = None
                if isinstance(exc, sqlite3.OperationalError) and any(
                    word in str(exc).lower() for word in ("locked", "busy")
                ):
                    raise
                self._quarantine()
                _warn_once("corrupt-db", "polling state database recovered from corrupt file")
            finally:
                if connection is not None:
                    connection.close()
            if connection is None:
                connection = self._connect()
                try:
                    connection.execute("PRAGMA journal_mode=WAL")
                    self._create_schema(connection)
                finally:
                    connection.close()

    @contextmanager
    def _write(self) -> Generator[sqlite3.Connection]:
        with _process_lock(self.lock_path):
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                with open(self.key_path, "rb") as key_file:
                    if key_file.read() != self._key:
                        raise ValueError("polling state key changed; reopen the store")
                row = connection.execute("SELECT value FROM meta WHERE key='key_sentinel'").fetchone()
                if row is None or _decrypt(self._key, row[0]) != _SENTINEL:
                    raise ValueError("polling state database changed; reopen the store")
                yield connection
                connection.execute("COMMIT")
            except Exception:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                connection.close()

    @contextmanager
    def _read(self) -> Generator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def record_observation(
        self, *, repo: str, item_type: str, number: int, activity_iso: str, now_epoch: float
    ) -> None:
        text = activity_iso.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            activity_epoch = parsed.timestamp()
            normalized_iso = activity_iso
        except ValueError:
            activity_epoch, normalized_iso = now_epoch, ""
        ident = (repo, item_type, number)
        if self.memory_only:
            with self._mutex:
                first = self._observations.get(ident, (now_epoch, 0.0, "", now_epoch))[0]
                self._observations[ident] = (first, activity_epoch, normalized_iso, now_epoch)
            return
        with self._write() as db:
            row = db.execute(
                "SELECT first_seen_epoch FROM observed_items WHERE repo=? AND item_type=? AND number=?", ident
            ).fetchone()
            first = row[0] if row else _token_float(self._key, now_epoch)
            db.execute(
                "INSERT OR REPLACE INTO observed_items VALUES(?,?,?,?,?,?,?)",
                (
                    *ident,
                    first,
                    _token_float(self._key, activity_epoch),
                    _encrypt(self._key, normalized_iso.encode()),
                    _token_float(self._key, now_epoch),
                ),
            )

    def get_observation(self, *, repo: str, item_type: str, number: int) -> ObservationRecord | None:
        ident = (repo, item_type, number)
        if self.memory_only:
            with self._mutex:
                row = self._observations.get(ident)
            return ObservationRecord(*ident, row[0], row[1], row[2]) if row else None
        with self._read() as db:
            row = db.execute(
                "SELECT first_seen_epoch,last_activity_epoch,last_activity_iso FROM observed_items WHERE repo=? AND item_type=? AND number=?",
                ident,
            ).fetchone()
        return (
            ObservationRecord(
                *ident,
                _float_token(self._key, row[0]),
                _float_token(self._key, row[1]),
                _decrypt(self._key, row[2]).decode(),
            )
            if row
            else None
        )

    def prune_observations(self, *, now_epoch: float, retention_days: float) -> int:
        cutoff = now_epoch - retention_days * 86400
        if self.memory_only:
            with self._mutex:
                old = [key for key, row in self._observations.items() if row[3] < cutoff]
                for key in old:
                    del self._observations[key]
                return len(old)
        with self._write() as db:
            rows = db.execute("SELECT repo,item_type,number,last_seen_epoch FROM observed_items").fetchall()
            old = [(r, t, n) for r, t, n, seen in rows if _float_token(self._key, seen) < cutoff]
            db.executemany("DELETE FROM observed_items WHERE repo=? AND item_type=? AND number=?", old)
            return len(old)

    def is_mention_processed(self, emit_key: str) -> bool:
        if self.memory_only:
            with self._mutex:
                return emit_key in self._mentions
        with self._read() as db:
            return db.execute("SELECT 1 FROM processed_mentions WHERE emit_key=?", (emit_key,)).fetchone() is not None

    def reserve_mention(
        self, *, emit_key: str, mention_key: str, repo: str, item_type: str, number: int, now_epoch: float
    ) -> bool:
        if self.memory_only:
            with self._mutex:
                if emit_key in self._mentions:
                    return False
                self._mentions[emit_key] = ProcessedMention(
                    emit_key, mention_key, repo, item_type, number, "reserved", now_epoch
                )
                return True
        with self._write() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO processed_mentions VALUES(?,?,?,?,?,?,?)",
                (emit_key, mention_key, repo, item_type, number, "reserved", _token_float(self._key, now_epoch)),
            )
            return cursor.rowcount == 1

    def ack_item_mentions(self, *, repo: str, item_type: str, number: int, now_epoch: float) -> int:
        if self.memory_only:
            with self._mutex:
                keys = [
                    key
                    for key, row in self._mentions.items()
                    if (row.repo, row.item_type, row.number, row.status) == (repo, item_type, number, "reserved")
                ]
                for key in keys:
                    row = self._mentions[key]
                    self._mentions[key] = ProcessedMention(
                        row.emit_key,
                        row.mention_key,
                        row.repo,
                        row.item_type,
                        row.number,
                        "processed",
                        row.recorded_epoch,
                    )
                return len(keys)
        with self._write() as db:
            cursor = db.execute(
                "UPDATE processed_mentions SET status='processed' WHERE repo=? AND item_type=? AND number=? AND status='reserved'",
                (repo, item_type, number),
            )
            return cursor.rowcount

    def release_stale_reservations(self, *, now_epoch: float, ttl_s: float) -> int:
        cutoff = now_epoch - ttl_s
        if self.memory_only:
            with self._mutex:
                keys = [
                    key
                    for key, row in self._mentions.items()
                    if row.status == "reserved" and row.recorded_epoch < cutoff
                ]
                for key in keys:
                    del self._mentions[key]
                return len(keys)
        with self._write() as db:
            rows = db.execute(
                "SELECT emit_key,recorded_epoch FROM processed_mentions WHERE status='reserved'"
            ).fetchall()
            keys = [key for key, epoch in rows if _float_token(self._key, epoch) < cutoff]
            db.executemany("DELETE FROM processed_mentions WHERE emit_key=?", [(key,) for key in keys])
            return len(keys)

    def list_processed_mentions(self) -> list[ProcessedMention]:
        if self.memory_only:
            with self._mutex:
                return list(self._mentions.values())
        with self._read() as db:
            rows = db.execute(
                "SELECT emit_key,mention_key,repo,item_type,number,status,recorded_epoch FROM processed_mentions"
            ).fetchall()
        return [ProcessedMention(a, b, c, d, e, f, _float_token(self._key, g)) for a, b, c, d, e, f, g in rows]

    def set_pending_anchor(self, *, mention_key: str, repo: str, item_type: str, number: int, now_epoch: float) -> None:
        anchor = PendingAnchor(mention_key, repo, item_type, number, now_epoch)
        if self.memory_only:
            with self._mutex:
                self._anchors[mention_key] = anchor
            return
        with self._write() as db:
            db.execute(
                "INSERT OR REPLACE INTO pending_anchors VALUES(?,?,?,?,?)",
                (mention_key, repo, item_type, number, _token_float(self._key, now_epoch)),
            )

    def remove_pending_anchor(self, mention_key: str) -> None:
        if self.memory_only:
            with self._mutex:
                self._anchors.pop(mention_key, None)
            return
        with self._write() as db:
            db.execute("DELETE FROM pending_anchors WHERE mention_key=?", (mention_key,))

    def list_pending_anchors(self) -> list[PendingAnchor]:
        if self.memory_only:
            with self._mutex:
                return list(self._anchors.values())
        with self._read() as db:
            rows = db.execute(
                "SELECT mention_key,repo,item_type,number,blocked_since_epoch FROM pending_anchors"
            ).fetchall()
        return [PendingAnchor(a, b, c, d, _float_token(self._key, e)) for a, b, c, d, e in rows]

    def set_policy_fingerprint(self, *, env_id: str, repo: str, fingerprint: str, now_epoch: float) -> None:
        if self.memory_only:
            with self._mutex:
                self._fingerprints[(env_id, repo)] = fingerprint
            return
        with self._write() as db:
            db.execute(
                "INSERT OR REPLACE INTO policy_fingerprints VALUES(?,?,?,?)",
                (env_id, repo, fingerprint, _token_float(self._key, now_epoch)),
            )

    def get_policy_fingerprint(self, *, env_id: str, repo: str) -> str | None:
        if self.memory_only:
            with self._mutex:
                return self._fingerprints.get((env_id, repo))
        with self._read() as db:
            row = db.execute(
                "SELECT fingerprint FROM policy_fingerprints WHERE env_id=? AND repo=?", (env_id, repo)
            ).fetchone()
        return row[0] if row else None


def get_polling_state_store() -> PollingStateStore:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            state_dir = os.path.dirname(os.path.abspath(default_state_path()))
            try:
                _singleton = PollingStateStore(
                    database_path=os.path.join(state_dir, "gh-polling-state.sqlite3"),
                    key_path=os.path.join(state_dir, "gh-polling-state.key"),
                    lock_path=os.path.join(state_dir, "gh-polling-state.lock"),
                )
            except Exception:
                _warn_once("memory-fallback", "polling state unavailable; using memory-only state")
                _singleton = PollingStateStore(database_path="", key_path="", lock_path="", memory_only=True)
        return _singleton


def reset_polling_state_store(store: PollingStateStore | None = None) -> None:
    global _singleton
    with _singleton_lock:
        _singleton = store
