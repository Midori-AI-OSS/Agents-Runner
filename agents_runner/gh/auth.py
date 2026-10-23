"""Shared, single-flight GitHub CLI authentication state."""

from __future__ import annotations

import os
import re
import json
import time
import uuid
import hashlib
import sqlite3
import tempfile
import threading

from enum import Enum
from typing import cast
from typing import Callable
from dataclasses import dataclass

from .process import run_gh
from .errors import GhManagementError
from agents_runner.persistence import default_state_path

_AUTH_CACHE_TTL_S = 300.0
_SHARED_AUTH_CACHE_TIMEOUT_S = 30.0
_SHARED_AUTH_CACHE_TABLE = "gh_auth_snapshot_v1"
_AUTH_LOGIN_PATTERN = re.compile(r"Logged in to .* account ([A-Za-z0-9-]+)")


class GhAuthError(Enum):
    """Failure state for an authentication status refresh."""

    NONE = "none"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class GhAuthSnapshot:
    """The authentication values produced by one ``gh auth status`` probe."""

    authenticated: bool
    login: str
    expires_at: float
    error: GhAuthError = GhAuthError.NONE


_cache_condition = threading.Condition()
_cached_snapshot: GhAuthSnapshot | None = None
_cached_shared_generation: str | None = None
_refreshing = False
_invalidation_generation = 0
_monotonic: Callable[[], float] = time.monotonic


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _as_object_dict(value: object) -> dict[object, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[object, object], value)


def _parse_login_from_auth_status(text: str) -> str:
    for line in str(text or "").splitlines():
        match = _AUTH_LOGIN_PATTERN.search(line)
        if match:
            return _safe_text(match.group(1)).lower()
    return ""


def _resolve_login_from_api(*, timeout_s: float) -> str:
    try:
        api_proc = run_gh(["gh", "api", "user", "-H", "Accept: application/vnd.github+json"], timeout_s=timeout_s)
    except GhManagementError:
        return ""
    if api_proc.returncode != 0:
        return ""
    try:
        data = json.loads(_safe_text(api_proc.stdout))
    except (TypeError, ValueError):
        return ""
    data_dict = _as_object_dict(data)
    if data_dict is None:
        return ""
    return _safe_text(data_dict.get("login")).lower()


def _refresh_snapshot(*, timeout_s: float) -> GhAuthSnapshot:
    try:
        proc = run_gh(["gh", "auth", "status"], timeout_s=timeout_s)
    except GhManagementError as exc:
        error = GhAuthError.TIMEOUT if "timed out" in str(exc).lower() else GhAuthError.UNAVAILABLE
        return GhAuthSnapshot(authenticated=False, login="", expires_at=_monotonic(), error=error)

    authenticated = proc.returncode == 0
    login = ""
    if authenticated:
        combined_output = "\n".join(part for part in (_safe_text(proc.stdout), _safe_text(proc.stderr)) if part)
        login = _parse_login_from_auth_status(combined_output)
        if not login:
            login = _resolve_login_from_api(timeout_s=timeout_s)
    return GhAuthSnapshot(authenticated=authenticated, login=login, expires_at=_monotonic() + _AUTH_CACHE_TTL_S)


def _shared_cache_key() -> str | None:
    if _monotonic is not time.monotonic:
        return None
    if any(os.environ.get(name) for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")):
        return None
    config_dir = os.environ.get("GH_CONFIG_DIR")
    if not config_dir:
        config_root = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        config_dir = os.path.join(config_root, "gh")
    normalized_config_dir = os.path.normcase(os.path.abspath(os.path.expanduser(config_dir)))
    host = _safe_text(os.environ.get("GH_HOST")) or "github.com"
    return hashlib.sha256(f"{normalized_config_dir}\n{host}".encode("utf-8")).hexdigest()


def _shared_cache_paths() -> tuple[str, str] | None:
    try:
        state_dir = os.path.dirname(os.path.abspath(default_state_path()))
        os.makedirs(state_dir, exist_ok=True)
    except (OSError, ValueError):
        return None
    return (
        os.path.join(state_dir, "gh-auth-cache.sqlite3"),
        os.path.join(state_dir, "gh-auth-cache-generation"),
    )


def _read_shared_cache_generation(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as generation_file:
            return generation_file.read().strip()
    except OSError:
        return ""


def _active_shared_cache_generation() -> str | None:
    cache_key = _shared_cache_key()
    if cache_key is None:
        return None
    paths = _shared_cache_paths()
    if paths is None:
        return None
    return f"{paths[0]}:{cache_key}:{_read_shared_cache_generation(paths[1])}"


def _advance_shared_cache_generation(path: str) -> None:
    """Invalidate disk snapshots without waiting for an in-progress auth probe."""

    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix="gh-auth-cache-generation-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as generation_file:
            generation_file.write(uuid.uuid4().hex)
        os.replace(temporary_path, path)
    finally:
        try:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
        except OSError:
            pass


def _snapshot_from_shared_row(row: tuple[object, ...]) -> GhAuthSnapshot | None:
    try:
        authenticated, login, error_value, expires_at_epoch = row
        if not isinstance(expires_at_epoch, (int, float)) or isinstance(expires_at_epoch, bool):
            return None
        remaining_s = float(expires_at_epoch) - time.time()
        if remaining_s <= 0.0:
            return None
        return GhAuthSnapshot(
            authenticated=bool(authenticated),
            login=_safe_text(login),
            expires_at=_monotonic() + remaining_s,
            error=GhAuthError(_safe_text(error_value)),
        )
    except (TypeError, ValueError):
        return None


def _refresh_shared(*, timeout_s: float, use_cache: bool, request_ns: int) -> tuple[GhAuthSnapshot, str | None]:
    cache_key = _shared_cache_key()
    if cache_key is None:
        return _refresh_snapshot(timeout_s=timeout_s), None
    paths = _shared_cache_paths()
    if paths is None:
        return _refresh_snapshot(timeout_s=timeout_s), None

    database_path, generation_path = paths
    connection = sqlite3.connect(database_path, timeout=_SHARED_AUTH_CACHE_TIMEOUT_S, isolation_level=None)
    try:
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {_SHARED_AUTH_CACHE_TABLE} ("
            "cache_key TEXT PRIMARY KEY, authenticated INTEGER NOT NULL, login TEXT NOT NULL, "
            "error TEXT NOT NULL, expires_at REAL NOT NULL, refreshed_at_ns INTEGER NOT NULL, generation TEXT NOT NULL)"
        )
        while True:
            generation = _read_shared_cache_generation(generation_path)
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    f"SELECT authenticated, login, error, expires_at, refreshed_at_ns, generation "
                    f"FROM {_SHARED_AUTH_CACHE_TABLE} WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
                if row is not None:
                    try:
                        cached_snapshot = _snapshot_from_shared_row(row[:4])
                        request_is_coalesced = use_cache or int(row[4]) > request_ns
                        if cached_snapshot is not None and row[5] == generation and request_is_coalesced:
                            connection.execute("COMMIT")
                            return cached_snapshot, f"{database_path}:{cache_key}:{generation}"
                    except (IndexError, TypeError, ValueError):
                        pass

                snapshot = _refresh_snapshot(timeout_s=timeout_s)
                current_generation = _read_shared_cache_generation(generation_path)
                if current_generation != generation:
                    connection.execute("ROLLBACK")
                    continue
                refreshed_at_ns = time.time_ns()
                expires_at_epoch = time.time() + max(0.0, snapshot.expires_at - _monotonic())
                connection.execute(
                    f"INSERT INTO {_SHARED_AUTH_CACHE_TABLE} "
                    "(cache_key, authenticated, login, error, expires_at, refreshed_at_ns, generation) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(cache_key) DO UPDATE SET authenticated = excluded.authenticated, "
                    "login = excluded.login, error = excluded.error, expires_at = excluded.expires_at, "
                    "refreshed_at_ns = excluded.refreshed_at_ns, generation = excluded.generation",
                    (
                        cache_key,
                        int(snapshot.authenticated),
                        snapshot.login,
                        snapshot.error.value,
                        expires_at_epoch,
                        refreshed_at_ns,
                        generation,
                    ),
                )
                connection.execute("COMMIT")
                return snapshot, f"{database_path}:{cache_key}:{generation}"
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
    finally:
        connection.close()


def get_gh_auth_snapshot(*, timeout_s: float = 10.0, use_cache: bool = True) -> GhAuthSnapshot:
    """Return one shared snapshot, coalescing refreshes across threads and processes."""

    global _cached_shared_generation, _cached_snapshot, _refreshing
    with _cache_condition:
        now_s = _monotonic()
        if use_cache and _cached_snapshot is not None and _cached_snapshot.expires_at > now_s:
            if _cached_shared_generation == _active_shared_cache_generation():
                return _cached_snapshot
            _cached_snapshot = None
            _cached_shared_generation = None
        if _refreshing:
            while _refreshing:
                _cache_condition.wait()
            if _cached_snapshot is not None:
                return _cached_snapshot
        _refreshing = True
        refresh_generation = _invalidation_generation
        requested_at_ns = time.time_ns()

    while True:
        try:
            try:
                snapshot, shared_generation = _refresh_shared(
                    timeout_s=timeout_s,
                    use_cache=use_cache,
                    request_ns=requested_at_ns,
                )
            except (OSError, sqlite3.Error):
                snapshot = _refresh_snapshot(timeout_s=timeout_s)
                shared_generation = _active_shared_cache_generation()
        except BaseException:
            with _cache_condition:
                _refreshing = False
                _cache_condition.notify_all()
            raise
        with _cache_condition:
            if refresh_generation != _invalidation_generation:
                refresh_generation = _invalidation_generation
                continue
            _cached_snapshot = snapshot
            _cached_shared_generation = shared_generation
            _refreshing = False
            _cache_condition.notify_all()
            return snapshot


def invalidate_gh_auth_cache() -> None:
    """Expire local and shared snapshots so the next query refreshes authentication."""

    global _cached_shared_generation, _cached_snapshot, _invalidation_generation
    with _cache_condition:
        _cached_snapshot = None
        _cached_shared_generation = None
        _invalidation_generation += 1
    paths = _shared_cache_paths() if _shared_cache_key() is not None else None
    if paths is not None:
        try:
            _advance_shared_cache_generation(paths[1])
        except OSError:
            pass
    from .rate_limiter import invalidate_all as _invalidate_rate_limiter

    _invalidate_rate_limiter()


def reset_gh_auth_cache(*, monotonic: Callable[[], float] = time.monotonic) -> None:
    """Reset local and shared cached state and its clock for deterministic verification."""

    global _cached_shared_generation, _cached_snapshot, _invalidation_generation, _monotonic
    with _cache_condition:
        if _refreshing:
            raise RuntimeError("cannot reset GitHub authentication cache during a refresh")
        _cached_snapshot = None
        _cached_shared_generation = None
        _invalidation_generation = 0
        _monotonic = monotonic
    paths = _shared_cache_paths() if _shared_cache_key() is not None else None
    if paths is not None:
        try:
            _advance_shared_cache_generation(paths[1])
        except OSError:
            pass


def is_gh_authenticated(*, timeout_s: float = 10.0, use_cache: bool = True) -> bool:
    return get_gh_auth_snapshot(timeout_s=timeout_s, use_cache=use_cache).authenticated


def resolve_authenticated_login(*, timeout_s: float = 10.0, use_cache: bool = True) -> str:
    return get_gh_auth_snapshot(timeout_s=timeout_s, use_cache=use_cache).login


def _rate_limit_resolver() -> str:
    return resolve_authenticated_login(timeout_s=5.0, use_cache=True)


from .rate_limiter import set_login_resolver as _set_login_resolver

_set_login_resolver(_rate_limit_resolver)
