"""Thread-safe tracking for MCP-launched task workers."""

from __future__ import annotations

import threading
import time

from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from typing import ClassVar
from typing import TypeVar

from agents_runner.docker.agent_worker import DockerAgentWorker
from agents_runner.execution.supervisor import TaskSupervisor


TrackedWorker = DockerAgentWorker | TaskSupervisor
TrackedThread = threading.Thread | None
TrackedFuture = Future[Any]
T = TypeVar("T")


@dataclass
class WorkerRecord:
    worker: TrackedWorker
    thread: TrackedThread
    future: TrackedFuture


class WorkerTracker:
    """Track MCP task workers and provide coordinated cancellation."""

    _instance: ClassVar["WorkerTracker | None"] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: dict[str, WorkerRecord] = {}
        self._executor = ThreadPoolExecutor(thread_name_prefix="agents-runner-mcp")
        self._shutdown = False

    @classmethod
    def instance(cls) -> "WorkerTracker":
        with cls._instance_lock:
            if cls._instance is None or cls._instance._shutdown:
                cls._instance = WorkerTracker()
            return cls._instance

    def submit(self, task_id: str, worker: TrackedWorker, runner: Callable[[], T]) -> Future[T]:
        task_id = str(task_id or "").strip()
        if not task_id:
            raise ValueError("task_id is required")
        if self._shutdown:
            raise RuntimeError("worker tracker is shut down")

        ready = threading.Event()

        def _runner() -> T:
            ready.wait()
            self._set_thread(task_id, threading.current_thread())
            return runner()

        future = self._executor.submit(_runner)
        self.register(task_id, worker, None, future)
        ready.set()
        return future

    def register(self, task_id: str, worker: TrackedWorker, thread: TrackedThread, future: TrackedFuture) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        with self._lock:
            self._workers[task_id] = WorkerRecord(worker=worker, thread=thread, future=future)

    def unregister(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        with self._lock:
            self._workers.pop(task_id, None)

    def get(self, task_id: str) -> WorkerRecord | None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return None
        with self._lock:
            return self._workers.get(task_id)

    def get_all_task_ids(self) -> list[str]:
        with self._lock:
            return list(self._workers.keys())

    def cancel(self, task_id: str) -> bool:
        record = self.get(task_id)
        if record is None:
            return False

        self._request_stop(record.worker)
        deadline_s = time.monotonic() + 1.0
        while not record.future.done() and time.monotonic() < deadline_s:
            time.sleep(0.05)

        if not record.future.done():
            self._request_kill(record.worker)
        return True

    def cancel_all(self) -> None:
        for task_id in self.get_all_task_ids():
            self.cancel(task_id)

    def shutdown(self, *, wait: bool = False) -> None:
        self._shutdown = True
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _set_thread(self, task_id: str, thread: threading.Thread) -> None:
        with self._lock:
            record = self._workers.get(task_id)
            if record is not None:
                record.thread = thread

    @staticmethod
    def _request_stop(worker: TrackedWorker) -> None:
        request_user_cancel = getattr(worker, "request_user_cancel", None)
        if callable(request_user_cancel):
            request_user_cancel()
            return
        worker.request_stop()

    @staticmethod
    def _request_kill(worker: TrackedWorker) -> None:
        request_user_kill = getattr(worker, "request_user_kill", None)
        if callable(request_user_kill):
            request_user_kill()
            return
        request_kill = getattr(worker, "request_kill", None)
        if callable(request_kill):
            request_kill()
            return
        worker.request_stop()


def get_worker_tracker() -> WorkerTracker:
    return WorkerTracker.instance()
