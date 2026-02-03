"""Animation orchestration for dashboard past tasks.

This module contains the PastTaskAnimator class that manages staggered entrance
animations for task rows in the past tasks tab. Extracted from dashboard.py to
maintain the 600-line hard limit per file.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtCore import QPoint
from PySide6.QtCore import QRect
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QScrollArea

from agents_runner.ui.pages.dashboard_row import TaskRow


class PastTaskAnimator:
    """Orchestrates staggered entrance animations for past task rows.

    This class manages the animation queue and timing for task rows appearing
    in the past tasks tab, creating a smooth staggered entrance effect as rows
    become visible in the viewport.
    """

    def __init__(
        self,
        scroll_area: QScrollArea,
        get_rows_callback: Callable[[], dict[str, TaskRow]],
        parent: QObject | None = None,
    ) -> None:
        """Initialize the animator.

        Args:
            scroll_area: The scroll area containing the task rows.
            get_rows_callback: Callable that returns the current dict of task rows.
            parent: Parent QObject for proper Qt lifecycle and thread affinity.
        """
        self._scroll = scroll_area
        self._get_rows = get_rows_callback
        self._parent = parent

        # Animation queue and tracking
        self._entrance_queue: list[TaskRow] = []
        self._entrance_seen: set[str] = set()

        # Timer for playing animations in sequence (parent it to avoid thread affinity issues)
        self._entrance_timer = QTimer(parent)
        self._entrance_timer.setSingleShot(True)
        self._entrance_timer.timeout.connect(self._play_next_entrance)

        # Timer for scanning visible rows (parent it to avoid thread affinity issues)
        self._visible_scan_reset_pending = False
        self._visible_scan_timer = QTimer(parent)
        self._visible_scan_timer.setSingleShot(True)
        self._visible_scan_timer.timeout.connect(self._queue_visible_entrances)

        # Connect to scroll events
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

    def cancel_entrances(self) -> None:
        """Cancel all pending entrance animations and clear the queue."""
        self._visible_scan_timer.stop()
        self._visible_scan_reset_pending = False

        self._entrance_timer.stop()
        self._entrance_queue.clear()

        for row in self._get_rows().values():
            row.cancel_entrance()

    def schedule_visible_entrances(self, *, reset: bool, delay_ms: int) -> None:
        """Schedule a scan for visible rows to animate.

        Args:
            reset: If True, clear the seen set and restart all animations.
            delay_ms: Delay before scanning for visible rows.
        """
        if reset:
            self._visible_scan_reset_pending = True
        self._visible_scan_timer.start(int(max(0, delay_ms)))

    def _queue_visible_entrances(self) -> None:
        """Scan for visible rows and queue them for animation."""
        if self._visible_scan_reset_pending:
            self._visible_scan_reset_pending = False
            self._entrance_seen.clear()
            stale_queue = list(self._entrance_queue)
            self._entrance_queue.clear()
            self._entrance_timer.stop()
            for row in stale_queue:
                if row is None or row.parent() is None:
                    continue
                row.cancel_entrance()

        queued = 0
        for row in self._rows_in_viewport():
            if queued >= 14:
                break
            task_id = row.task_id
            if not task_id or task_id in self._entrance_seen:
                continue
            row.cancel_entrance()
            if self._queue_entrance(row):
                queued += 1

    def _queue_entrance(self, row: TaskRow) -> bool:
        """Queue a single row for entrance animation.

        Args:
            row: The TaskRow to animate.

        Returns:
            True if the row was queued, False if it was already in the queue.
        """
        if row in self._entrance_queue:
            return False
        if row.task_id:
            self._entrance_seen.add(row.task_id)
        row.prepare_entrance(distance=36)
        self._entrance_queue.append(row)
        if not self._entrance_timer.isActive():
            self._entrance_timer.start(0)
        return True

    def _play_next_entrance(self) -> None:
        """Play the next entrance animation in the queue."""
        while self._entrance_queue:
            row = self._entrance_queue.pop(0)
            if row is None or row.parent() is None:
                continue
            if not row.isVisible():
                row.cancel_entrance()
                continue
            row.play_entrance(distance=36, fade_ms=120, move_ms=220)
            break
        if self._entrance_queue:
            self._entrance_timer.start(65)

    def _row_intersects_viewport(self, row: TaskRow) -> bool:
        """Check if a row intersects the viewport.

        Args:
            row: The TaskRow to check.

        Returns:
            True if the row is visible in the viewport.
        """
        if row.parent() is None or not row.isVisible():
            return False
        viewport = self._scroll.viewport()
        top_left = row.mapTo(viewport, QPoint(0, 0))
        rect = QRect(top_left, row.size())
        return viewport.rect().intersects(rect)

    def _rows_in_viewport(self) -> list[TaskRow]:
        """Get all rows currently visible in the viewport.

        Returns:
            List of TaskRows sorted by vertical position.
        """
        rows: list[TaskRow] = []
        for row in self._get_rows().values():
            if self._row_intersects_viewport(row):
                rows.append(row)
        rows.sort(key=lambda r: r.y())
        return rows

    def _on_scroll_changed(self, _value: int) -> None:
        """Handle scroll position changes."""
        self.schedule_visible_entrances(reset=False, delay_ms=35)

    def on_tab_shown(self) -> None:
        """Call when the past tasks tab becomes visible."""
        self.schedule_visible_entrances(reset=False, delay_ms=0)

    def on_past_task_added(self) -> None:
        """Call when a new past task is added."""
        self.schedule_visible_entrances(reset=False, delay_ms=0)
