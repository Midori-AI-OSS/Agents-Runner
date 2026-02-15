from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtCore import Slot


class InteractivePrepBridge(QObject):
    def __init__(
        self,
        *,
        on_stage: Callable[[str, str, str], None],
        on_log: Callable[[str, str], None],
        on_succeeded: Callable[[str, dict[str, Any]], None],
        on_failed: Callable[[str, str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_stage = on_stage
        self._on_log = on_log
        self._on_succeeded = on_succeeded
        self._on_failed = on_failed

    @Slot(str, str, str)
    def on_stage(self, task_id: str, status: str, message: str) -> None:
        self._on_stage(
            str(task_id or "").strip(), str(status or ""), str(message or "")
        )

    @Slot(str, str)
    def on_log(self, task_id: str, line: str) -> None:
        self._on_log(str(task_id or "").strip(), str(line or ""))

    @Slot(str, object)
    def on_succeeded(self, task_id: str, payload: object) -> None:
        payload_dict = payload if isinstance(payload, dict) else {}
        self._on_succeeded(str(task_id or "").strip(), payload_dict)

    @Slot(str, str)
    def on_failed(self, task_id: str, error_message: str) -> None:
        self._on_failed(str(task_id or "").strip(), str(error_message or ""))
