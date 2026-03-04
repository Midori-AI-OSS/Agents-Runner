from __future__ import annotations

import threading

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BufferedTaskEvent:
    kind: str
    payload: Any


class TaskEventProxy:
    """Thread-safe per-task buffer used to reduce UI-thread signal pressure."""

    def __init__(self, *, task_id: str, max_events: int = 8000) -> None:
        self.task_id = str(task_id or "").strip()
        self._max_events = max(200, int(max_events))
        self._events: deque[BufferedTaskEvent] = deque()
        self._lock = threading.Lock()
        self._dropped_log_lines = 0
        self._dropped_other_events = 0
        self._bridge_done_seen = False
        self._bridge_done_dispatched = False

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._dropped_log_lines = 0
            self._dropped_other_events = 0
            self._bridge_done_seen = False
            self._bridge_done_dispatched = False

    def enqueue_state(self, task_id: str, state: dict[str, Any]) -> None:
        if self._ignore_event(task_id):
            return
        self._enqueue("state", dict(state or {}))

    def enqueue_log(self, task_id: str, line: str) -> None:
        if self._ignore_event(task_id):
            return
        self._enqueue("log", str(line or ""))

    def enqueue_retry(
        self, task_id: str, attempt_number: int, agent: str, delay: float
    ) -> None:
        if self._ignore_event(task_id):
            return
        self._enqueue(
            "retry",
            (
                int(attempt_number),
                str(agent or ""),
                float(delay),
            ),
        )

    def enqueue_agent_switched(
        self, task_id: str, from_agent: str, to_agent: str
    ) -> None:
        if self._ignore_event(task_id):
            return
        self._enqueue(
            "agent_switched",
            (
                str(from_agent or ""),
                str(to_agent or ""),
            ),
        )

    def enqueue_done(
        self,
        task_id: str,
        exit_code: int,
        error: object,
        artifacts: list[Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        normalized_task_id = str(task_id or "").strip()
        if normalized_task_id != self.task_id:
            return
        with self._lock:
            if self._bridge_done_seen:
                return
            self._bridge_done_seen = True
            self._append_locked(
                BufferedTaskEvent(
                    "done",
                    (
                        int(exit_code),
                        error,
                        list(artifacts or []),
                        dict(metadata or {}),
                    ),
                )
            )

    def enqueue_host_log(self, task_id: str, line: str) -> None:
        normalized_task_id = str(task_id or "").strip()
        if normalized_task_id != self.task_id:
            return
        self._enqueue("host_log", str(line or ""))

    def drain(self, *, max_events: int = 500) -> list[BufferedTaskEvent]:
        limit = max(1, int(max_events))
        drained: list[BufferedTaskEvent] = []
        with self._lock:
            if self._dropped_log_lines > 0:
                drained.append(
                    BufferedTaskEvent(
                        "log",
                        (
                            "[ui/proxy] "
                            f"dropped {self._dropped_log_lines} buffered log line(s)"
                        ),
                    )
                )
                self._dropped_log_lines = 0
            if self._dropped_other_events > 0:
                drained.append(
                    BufferedTaskEvent(
                        "log",
                        (
                            "[ui/proxy] "
                            f"dropped {self._dropped_other_events} buffered event(s)"
                        ),
                    )
                )
                self._dropped_other_events = 0
            while self._events and len(drained) < limit:
                drained.append(self._events.popleft())
        return drained

    def has_pending(self) -> bool:
        with self._lock:
            return bool(
                self._events or self._dropped_log_lines or self._dropped_other_events
            )

    def mark_bridge_done_dispatched(self) -> None:
        with self._lock:
            self._bridge_done_dispatched = True

    def releasable(self) -> bool:
        with self._lock:
            return (
                self._bridge_done_dispatched
                and not self._events
                and self._dropped_log_lines == 0
                and self._dropped_other_events == 0
            )

    def _ignore_event(self, task_id: str) -> bool:
        normalized_task_id = str(task_id or "").strip()
        if normalized_task_id != self.task_id:
            return True
        with self._lock:
            return self._bridge_done_seen

    def _enqueue(self, kind: str, payload: Any) -> None:
        with self._lock:
            self._append_locked(BufferedTaskEvent(kind=kind, payload=payload))

    def _append_locked(self, event: BufferedTaskEvent) -> None:
        while len(self._events) >= self._max_events:
            ev = self._events.popleft()
            if ev.kind in {"log", "host_log"}:
                self._dropped_log_lines += 1
            else:
                self._dropped_other_events += 1
        self._events.append(event)
