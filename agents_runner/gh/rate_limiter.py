"""GitHub API rate-limiter using per-account token-bucket scheduling."""

from __future__ import annotations

import datetime
import enum
import re
import threading
import time

from typing import Callable

from midori_ai_logger import MidoriAiLogger


_monotonic = time.monotonic
_module_lock = threading.Lock()
_buckets: dict[tuple[str, str], _TokenBucket] = {}
_rate_limit_guard = threading.local()
_priority_stack = threading.local()

_login_resolver: Callable[[], str] = lambda: ""
logger = MidoriAiLogger(channel=None, name=__name__)


class Priority(enum.Enum):
    HIGH = "high"
    LOW = "low"


class push_priority:
    """Context manager that pushes a priority onto the thread-local stack.

    All ``run_gh`` calls within the context acquire permits at the
    pushed priority level.  Supports nesting — the innermost push
    takes precedence.
    """

    def __init__(self, priority: Priority) -> None:
        self._priority: Priority = priority

    def __enter__(self) -> None:
        stack = _get_priority_stack()
        stack.append(self._priority)

    def __exit__(self, *_: object) -> None:
        stack = _get_priority_stack()
        if stack:
            stack.pop()


def _get_priority_stack() -> list[Priority]:
    try:
        return _priority_stack.values
    except AttributeError:
        _priority_stack.values = []
        return _priority_stack.values


def _current_priority() -> Priority:
    stack = _get_priority_stack()
    if stack:
        return stack[-1]
    return Priority.LOW


_RATE_LIMIT_MARKER_RE = re.compile(
    r"rate limit exceeded|api rate limit exceeded|secondary rate limit|abuse detection",
    re.IGNORECASE,
)

_retry_after_re = re.compile(r"retry-after:\s*(\d+)", re.IGNORECASE)
_reset_epoch_re = re.compile(r"x-ratelimit-reset:\s*(\d+)", re.IGNORECASE)
_iso_ts_re = re.compile(
    r"(?:until|resets?\s*at)\s+(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})",
    re.IGNORECASE,
)
_relative_duration_re = re.compile(
    r"in\s+(\d+)\s+(second|minute|hour)s?",
    re.IGNORECASE,
)

_last_rate_limit_log: dict[tuple[str, str], float] = {}


def _read_rate_from_state() -> float:
    try:
        from agents_runner.persistence import default_state_path, load_state
    except Exception:
        return 2.0
    try:
        state = load_state(default_state_path())
        raw_rate = state.get("settings", {}).get("github_requests_per_second", 2)
        rate_int = int(raw_rate)
        if rate_int < 1 or rate_int > 10:
            logger.warning(
                "github_requests_per_second %d is outside valid range [1, 10]; clamping.",
                rate_int,
            )
        return float(max(1, min(10, rate_int)))
    except Exception:
        return 2.0


class _TokenBucket:
    def __init__(self, rate: float) -> None:
        self._rate: float = rate
        self._capacity: float = rate
        self._tokens: float = rate
        self._last_refill: float = _monotonic()
        self._condition: threading.Condition = threading.Condition()
        self._pause_until: float | None = None
        self._high_waiters: int = 0

    def pause(self, seconds: float) -> None:
        """Drain tokens, block refills for the given duration, and wake waiters."""
        with self._condition:
            self._tokens = 0.0
            self._pause_until = _monotonic() + seconds
            self._condition.notify_all()

    def consume(self, priority: Priority = Priority.LOW) -> None:
        """Acquire one permit, serving HIGH-priority callers before LOW.

        When a LOW-priority caller is waiting and a HIGH-priority caller
        arrives, the HIGH caller is served first once tokens become
        available.  Within the same priority tier, callers proceed in
        FIFO order.
        """
        is_high = priority == Priority.HIGH
        with self._condition:
            if is_high:
                self._high_waiters += 1
            try:
                while True:
                    if self._pause_until is not None:
                        remaining = max(0.0, self._pause_until - _monotonic())
                        if remaining <= 0.0:
                            self._pause_until = None
                        else:
                            self._condition.wait(timeout=remaining)
                            continue

                    self._refill()

                    blocked = not is_high and self._high_waiters > 0

                    if self._tokens >= 1.0 and not blocked:
                        self._tokens -= 1.0
                        self._condition.notify_all()
                        return

                    if self._tokens < 1.0:
                        deficit = 1.0 - self._tokens
                        wait = deficit / self._rate
                    else:
                        wait = 0.05

                    self._condition.wait(timeout=wait)
            finally:
                if is_high:
                    self._high_waiters -= 1
                    self._condition.notify_all()

    def _refill(self) -> None:
        now = _monotonic()
        if self._pause_until is not None and now < self._pause_until:
            self._last_refill = now
            self._tokens = 0.0
            return
        self._pause_until = None
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

    Priority is read from the thread-local context stack (set by
    callers via ``push_priority``) and defaults to ``LOW``.
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
        _consume(login, "github.com", priority=_current_priority())
    finally:
        _rate_limit_guard.active = False


def _consume(login: str, host: str, *, priority: Priority = Priority.LOW) -> None:
    if not login:
        return
    key = (login, host)
    with _module_lock:
        bucket = _buckets.get(key)
        if bucket is None:
            bucket = _TokenBucket(_read_rate_from_state())
            _buckets[key] = bucket
    bucket.consume(priority=priority)


def invalidate_all() -> None:
    """Clear all cached buckets and pause state (called on auth cache invalidation)."""
    with _module_lock:
        _buckets.clear()
        _last_rate_limit_log.clear()


def _parse_rate_limit_seconds(stderr: str, stdout: str) -> float | None:
    """Inspect stderr/stdout for rate-limit markers and extract pause duration.

    Returns the number of seconds to pause, or ``None`` if no rate-limit
    signal was found.
    """
    combined = ((stderr or "") + "\n" + (stdout or "")).lower()
    if not _RATE_LIMIT_MARKER_RE.search(combined):
        return None
    # Retry-After header (seconds)
    m = _retry_after_re.search(combined)
    if m:
        return float(m.group(1))
    # X-RateLimit-Reset header (epoch)
    m = _reset_epoch_re.search(combined)
    if m:
        seconds = int(m.group(1)) - int(time.time())
        return max(1.0, float(seconds))
    # ISO-8601 timestamp
    m = _iso_ts_re.search(combined)
    if m:
        try:
            ts_str = m.group(1).replace("T", " ").replace("Z", "")
            ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            seconds = ts.timestamp() - time.time()
            return max(1.0, float(seconds))
        except ValueError:
            pass
    # Relative duration ("in 47 seconds", "in 5 minutes")
    m = _relative_duration_re.search(combined)
    if m:
        value = int(m.group(1))
        unit = m.group(2).lower()
        if unit == "second":
            return float(value)
        if unit == "minute":
            return float(value * 60)
        if unit == "hour":
            return float(value * 3600)
    return 300.0


def _describe_source(stderr: str, stdout: str, pause_seconds: float) -> str:
    """Return a short label describing where the pause duration came from."""
    combined = (stderr or "") + "\n" + (stdout or "")
    if _retry_after_re.search(combined):
        return f"retry-after={pause_seconds:.0f}s"
    if _reset_epoch_re.search(combined):
        return f"x-ratelimit-reset={pause_seconds:.0f}s"
    if _iso_ts_re.search(combined):
        return f"timestamp={pause_seconds:.0f}s"
    if _relative_duration_re.search(combined):
        return f"relative={pause_seconds:.0f}s"
    return f"fallback={pause_seconds:.0f}s"


def check_and_handle_rate_limit(args: list[str], stderr: str, stdout: str) -> None:
    """Inspect failed ``gh`` command output and pause the account's rate-limiter.

    This is called immediately after ``run_gh`` when a subprocess returns a
    non-zero exit code.  It checks for rate-limit signals and, when found,
    drains the token bucket for the affected account and pauses all future
    permits until the extracted reset window elapses.

    Duplicate rate-limit events for the same account+reset-window are
    silently suppressed so only one ``[gh-rate-limit]`` log entry is emitted
    per event.
    """
    executable = args[0] if args else ""
    if executable != "gh":
        return
    if not stderr and not stdout:
        return
    pause_seconds = _parse_rate_limit_seconds(stderr, stdout)
    if pause_seconds is None:
        return
    login = _login_resolver()
    if not login:
        return
    account_key = (login, "github.com")
    with _module_lock:
        bucket = _buckets.get(account_key)
        if bucket is None:
            bucket = _TokenBucket(_read_rate_from_state())
            _buckets[account_key] = bucket
    bucket.pause(pause_seconds)
    expected_pause_until = _monotonic() + pause_seconds
    last_logged = _last_rate_limit_log.get(account_key)
    if last_logged is not None and abs(last_logged - expected_pause_until) < 1.0:
        return
    _last_rate_limit_log[account_key] = expected_pause_until
    source = _describe_source(stderr, stdout, pause_seconds)
    logger.info(
        "[gh-rate-limit] account=%s host=%s pause=%.0fs source=%s",
        login,
        "github.com",
        pause_seconds,
        source,
    )
