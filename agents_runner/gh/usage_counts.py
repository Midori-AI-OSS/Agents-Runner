"""In-memory counters for programmatic GitHub CLI launches made by this app process."""

import threading
import time

from collections import deque
from dataclasses import dataclass

_BUCKET_COUNT = 60


@dataclass(frozen=True)
class GhUsageSnapshot:
    """Immutable snapshot of gh launch totals."""

    total: int
    buckets: tuple[int, ...]


_lock = threading.Lock()
_total = 0
_buckets: deque[int] = deque([0] * _BUCKET_COUNT, maxlen=_BUCKET_COUNT)
_last_minute: int | None = None


def _roll_locked(now_minute: int) -> None:
    global _last_minute
    if _last_minute is None:
        _last_minute = now_minute
        return
    delta = now_minute - _last_minute
    if delta <= 0:
        return
    _last_minute = now_minute
    if delta >= _BUCKET_COUNT:
        _buckets.clear()
        _buckets.extend([0] * _BUCKET_COUNT)
        return
    for _ in range(delta):
        _buckets.append(0)


def record_gh_launch() -> None:
    global _total
    with _lock:
        _total += 1
        _roll_locked(int(time.time()) // 60)
        _buckets[-1] += 1


def snapshot() -> GhUsageSnapshot:
    with _lock:
        _roll_locked(int(time.time()) // 60)
        return GhUsageSnapshot(total=_total, buckets=tuple(_buckets))
