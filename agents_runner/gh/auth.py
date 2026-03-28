from __future__ import annotations

import json
import re
import threading
import time

from typing import cast

from .process import run_gh

_AUTH_CACHE_TTL_S = 15.0
_AUTH_LOGIN_PATTERN = re.compile(r"Logged in to .* account ([A-Za-z0-9-]+)")

_cache_lock = threading.Lock()
_cached_auth_ready = False
_cached_auth_expires_at = 0.0
_cached_login = ""
_cached_login_expires_at = 0.0


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _as_object_dict(value: object) -> dict[object, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[object, object], value)


def _cache_auth_state(value: bool, *, now_s: float) -> None:
    global _cached_auth_ready, _cached_auth_expires_at
    _cached_auth_ready = bool(value)
    _cached_auth_expires_at = now_s + _AUTH_CACHE_TTL_S


def _cache_login(value: str, *, now_s: float) -> str:
    global _cached_login, _cached_login_expires_at
    _cached_login = _safe_text(value).lower()
    _cached_login_expires_at = now_s + _AUTH_CACHE_TTL_S
    return _cached_login


def _parse_login_from_auth_status(text: str) -> str:
    for line in str(text or "").splitlines():
        match = _AUTH_LOGIN_PATTERN.search(line)
        if not match:
            continue
        return _safe_text(match.group(1)).lower()
    return ""


def is_gh_authenticated(*, timeout_s: float = 10.0, use_cache: bool = True) -> bool:
    now_s = time.time()
    if use_cache:
        with _cache_lock:
            if _cached_auth_expires_at > now_s:
                return _cached_auth_ready

    proc = run_gh(["gh", "auth", "status"], timeout_s=timeout_s)
    ready = proc.returncode == 0
    with _cache_lock:
        _cache_auth_state(ready, now_s=now_s)
    return ready


def resolve_authenticated_login(
    *, timeout_s: float = 10.0, use_cache: bool = True
) -> str:
    now_s = time.time()
    if use_cache:
        with _cache_lock:
            if _cached_login_expires_at > now_s:
                return _cached_login

    status_proc = run_gh(["gh", "auth", "status"], timeout_s=timeout_s)
    login = ""
    if status_proc.returncode == 0:
        combined = _safe_text(status_proc.stdout) or _safe_text(status_proc.stderr)
        login = _parse_login_from_auth_status(combined)
        with _cache_lock:
            _cache_auth_state(True, now_s=now_s)
    else:
        with _cache_lock:
            _cache_auth_state(False, now_s=now_s)
        if use_cache:
            with _cache_lock:
                return _cache_login("", now_s=now_s)
        return ""

    if login:
        with _cache_lock:
            return _cache_login(login, now_s=now_s)

    api_proc = run_gh(
        [
            "gh",
            "api",
            "user",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        timeout_s=timeout_s,
    )
    if api_proc.returncode != 0:
        with _cache_lock:
            return _cache_login("", now_s=now_s)

    payload = _safe_text(api_proc.stdout)
    if not payload:
        with _cache_lock:
            return _cache_login("", now_s=now_s)

    try:
        data = json.loads(payload)
    except Exception:
        with _cache_lock:
            return _cache_login("", now_s=now_s)

    data_dict = _as_object_dict(data)
    if data_dict is None:
        with _cache_lock:
            return _cache_login("", now_s=now_s)

    parsed_login = _safe_text(data_dict.get("login")).lower()
    with _cache_lock:
        return _cache_login(parsed_login, now_s=now_s)
