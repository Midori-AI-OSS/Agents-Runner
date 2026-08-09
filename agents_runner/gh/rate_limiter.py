"""GitHub API rate-limiter using per-account token-bucket scheduling."""

from __future__ import annotations

import threading
import time

from typing import Callable


_monotonic = time.monotonic
_module_lock = threading.Lock()
_buckets: dict[tuple[str, str], _TokenBucket] = {}
_rate_limit_guard = threading.local()

_login_resolver: Callable[[], str] = lambda: ""


def _read_rate_from_state() -> float:
    try:
        from agents_runner.persistence import default_state_path, load_state
    except Exception:
        return 2.0
    try:
        state = load_state(default_state_path())
        rate = state.get("settings", {}).get("github_requests_per_second", 2)
        return float(max(1, min(10, int(rate))))
    except Exception:
        return 2.0


class _TokenBucket:
    def __init__(self, rate: float) -> None:
        self._rate: float = rate
        self._capacity: float = rate
        self._tokens: float = rate
        self._last_refill: float = _monotonic()
        self._lock: threading.Lock = threading.Lock()

    def consume(self) -> None:
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            deficit = 1.0 - self._tokens
        time.sleep(deficit / self._rate)
        with self._lock:
            self._refill()
            self._tokens -= 1.0

    def _refill(self) -> None:
        now = _monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now


def set_login_resolver(resolver: Callable[[], str]) -> None:
    global _login_resolver
    _login_resolver = resolver


def acquire(args: list[str]) -> None:
    """Rate-limit gate called before every gh CLI subprocess invocation.

    Skips git commands, auth status/login probes, and unknown-account
    calls (which handles the bootstrap case where login resolution
    itself triggers a ``run_gh`` call).
    """
    if not args:
        return
    executable = args[0]
    if executable == "git":
        return
    if executable == "gh" and len(args) >= 3 and args[1] == "auth" and args[2] in ("status", "login"):
        return
    if getattr(_rate_limit_guard, "active", False):
        return
    _rate_limit_guard.active = True
    try:
        login = _login_resolver()
        if not login:
            return
        _consume(login, "github.com")
    finally:
        _rate_limit_guard.active = False


def _consume(login: str, host: str) -> None:
    if not login:
        return
    key = (login, host)
    with _module_lock:
        bucket = _buckets.get(key)
        if bucket is None:
            bucket = _TokenBucket(_read_rate_from_state())
            _buckets[key] = bucket
    bucket.consume()


def invalidate_all() -> None:
    """Clear all cached buckets (called on auth cache invalidation)."""
    with _module_lock:
        _buckets.clear()
