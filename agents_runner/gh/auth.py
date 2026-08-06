"""Shared, single-flight GitHub CLI authentication state."""

from __future__ import annotations

import json
import re
import threading
import time

from dataclasses import dataclass
from enum import Enum
from typing import Callable
from typing import cast

from .errors import GhManagementError
from .process import run_gh

_AUTH_CACHE_TTL_S = 300.0
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
_refreshing = False
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
        return GhAuthSnapshot(authenticated=False, login="", expires_at=_monotonic() + _AUTH_CACHE_TTL_S, error=error)

    authenticated = proc.returncode == 0
    login = ""
    if authenticated:
        combined_output = "\n".join(part for part in (_safe_text(proc.stdout), _safe_text(proc.stderr)) if part)
        login = _parse_login_from_auth_status(combined_output)
        if not login:
            login = _resolve_login_from_api(timeout_s=timeout_s)
    return GhAuthSnapshot(authenticated=authenticated, login=login, expires_at=_monotonic() + _AUTH_CACHE_TTL_S)


def get_gh_auth_snapshot(*, timeout_s: float = 10.0, use_cache: bool = True) -> GhAuthSnapshot:
    """Return one shared snapshot, coalescing concurrent normal and forced refreshes."""

    global _cached_snapshot, _refreshing
    with _cache_condition:
        now_s = _monotonic()
        if use_cache and _cached_snapshot is not None and _cached_snapshot.expires_at > now_s:
            return _cached_snapshot
        if _refreshing:
            while _refreshing:
                _cache_condition.wait()
            if _cached_snapshot is not None:
                return _cached_snapshot
        _refreshing = True

    try:
        snapshot = _refresh_snapshot(timeout_s=timeout_s)
    except BaseException:
        with _cache_condition:
            _refreshing = False
            _cache_condition.notify_all()
        raise
    with _cache_condition:
        _cached_snapshot = snapshot
        _refreshing = False
        _cache_condition.notify_all()
    return snapshot


def invalidate_gh_auth_cache() -> None:
    """Expire the current snapshot so the next authentication query refreshes it."""

    global _cached_snapshot
    with _cache_condition:
        _cached_snapshot = None


def reset_gh_auth_cache(*, monotonic: Callable[[], float] = time.monotonic) -> None:
    """Reset cached state and its clock for deterministic verification."""

    global _cached_snapshot, _monotonic
    with _cache_condition:
        if _refreshing:
            raise RuntimeError("cannot reset GitHub authentication cache during a refresh")
        _cached_snapshot = None
        _monotonic = monotonic


def is_gh_authenticated(*, timeout_s: float = 10.0, use_cache: bool = True) -> bool:
    return get_gh_auth_snapshot(timeout_s=timeout_s, use_cache=use_cache).authenticated


def resolve_authenticated_login(*, timeout_s: float = 10.0, use_cache: bool = True) -> str:
    return get_gh_auth_snapshot(timeout_s=timeout_s, use_cache=use_cache).login
