from __future__ import annotations

import time

from dataclasses import dataclass

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from agents_runner.environments.task_workspaces import move_task_workspace


@dataclass(frozen=True)
class TaskWorkspaceMigrationRecord:
    task_id: str
    environment_id: str


@dataclass(frozen=True)
class TaskWorkspaceMigrationMoved:
    task_id: str
    environment_id: str
    destination: str


class TaskWorkspaceMigrationWorker(QObject):
    progress = Signal(int, int, str, str)
    finished = Signal(int, int, int, object, object)

    def __init__(
        self,
        *,
        records: list[TaskWorkspaceMigrationRecord],
        data_dir: str,
        source_location: str,
        destination_location: str,
    ) -> None:
        super().__init__()
        self._records = list(records)
        self._data_dir = str(data_dir or "")
        self._source_location = str(source_location or "")
        self._destination_location = str(destination_location or "")

    @Slot()
    def run(self) -> None:
        total = len(self._records)
        moved = 0
        skipped = 0
        failed = 0
        failures: list[str] = []
        moved_records: list[TaskWorkspaceMigrationMoved] = []
        started_s = time.monotonic()

        for index, record in enumerate(self._records, start=1):
            task_id = str(record.task_id or "").strip()
            self.progress.emit(
                index - 1, total, task_id, self._eta_text(index - 1, total, started_s)
            )
            result = move_task_workspace(
                env_id=record.environment_id,
                task_id=record.task_id,
                data_dir=self._data_dir,
                source_location=self._source_location,
                destination_location=self._destination_location,
            )
            if result.moved:
                moved += 1
                moved_records.append(
                    TaskWorkspaceMigrationMoved(
                        task_id=record.task_id,
                        environment_id=record.environment_id,
                        destination=result.destination,
                    )
                )
            elif result.skipped:
                skipped += 1
            else:
                failed += 1
                failures.append(f"{record.task_id}: {result.error}")
            self.progress.emit(
                index, total, task_id, self._eta_text(index, total, started_s)
            )

        self.finished.emit(moved, skipped, failed, failures, moved_records)

    @staticmethod
    def _eta_text(completed: int, total: int, started_s: float) -> str:
        if completed <= 0 or total <= completed:
            return "Estimating..." if completed <= 0 and total > 0 else "Done"
        elapsed = max(0.0, time.monotonic() - started_s)
        per_item = elapsed / float(completed)
        remaining_s = max(0.0, per_item * float(total - completed))
        if remaining_s < 60:
            return f"{remaining_s:.0f}s remaining"
        return f"{remaining_s / 60.0:.1f}m remaining"
