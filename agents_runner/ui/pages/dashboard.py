from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtGui import QHideEvent
from PySide6.QtGui import QLinearGradient
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QPainter
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QTabBar
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.pages.dashboard_animations import PastTaskAnimator
from agents_runner.ui.pages.dashboard_loader import PastTaskProgressiveLoader
from agents_runner.ui.pages.dashboard_row import TaskRow
from agents_runner.ui.task_model import Task


class _DashboardScrim(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DashboardScrim")
        self._alpha = 92
        self._feather_px = 38

    def paintEvent(self, event: QPaintEvent) -> None:
        w = int(self.width())
        h = int(self.height())
        if w <= 0 or h <= 0:
            return

        feather = int(min(self._feather_px, h // 2))
        alpha = int(min(max(self._alpha, 0), 255))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        if feather <= 0 or alpha <= 0:
            return

        # Center band (full width), leaving feather at top/bottom only.
        painter.fillRect(
            0,
            feather,
            w,
            h - feather * 2,
            QColor(0, 0, 0, alpha),
        )

        # Feather top/bottom edges.
        top = QLinearGradient(0, 0, 0, feather)
        top.setColorAt(0.0, QColor(0, 0, 0, 0))
        top.setColorAt(1.0, QColor(0, 0, 0, alpha))
        painter.fillRect(0, 0, w, feather, top)

        bottom = QLinearGradient(0, h - feather, 0, h)
        bottom.setColorAt(0.0, QColor(0, 0, 0, alpha))
        bottom.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, h - feather, w, feather, bottom)


class DashboardPage(QWidget):
    task_selected = Signal(str)
    clean_old_requested = Signal()
    task_discard_requested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        load_past_batch_callback: Callable[[int, int], int] | None = None,
    ) -> None:
        super().__init__(parent)
        self._selected_task_id: str | None = None
        self._filter_text_tokens: list[str] = []
        self._load_past_batch_callback = load_past_batch_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        table = _DashboardScrim()
        table_layout = QVBoxLayout(table)
        table_layout.setContentsMargins(0, 12, 0, 12)
        table_layout.setSpacing(0)

        filters = QWidget()
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(12, 0, 12, 0)
        filters_layout.setSpacing(10)

        self._filter_text = QLineEdit()
        self._filter_text.setPlaceholderText("Filter tasks…")
        self._filter_text.textChanged.connect(self._on_filter_changed)

        self._filter_environment = QComboBox()
        self._filter_environment.setFixedWidth(240)
        self._filter_environment.addItem("All environments", "")
        self._filter_environment.currentIndexChanged.connect(self._on_filter_changed)

        self._filter_state = QComboBox()
        self._filter_state.setFixedWidth(160)
        self._filter_state.addItem("Any state", "any")
        self._filter_state.addItem("Active", "active")
        self._filter_state.addItem("Done", "done")
        self._filter_state.addItem("Failed", "failed")
        self._filter_state.currentIndexChanged.connect(self._on_filter_changed)

        clear_filters = QToolButton()
        clear_filters.setObjectName("RowTrash")
        clear_filters.setIcon(lucide_icon("rotate-ccw"))
        clear_filters.setToolButtonStyle(Qt.ToolButtonIconOnly)
        clear_filters.setToolTip("Clear filters")
        clear_filters.setAccessibleName("Clear filters")
        clear_filters.clicked.connect(self._clear_filters)

        self._btn_clean_old = QToolButton()
        self._btn_clean_old.setObjectName("RowTrash")
        self._btn_clean_old.setIcon(lucide_icon("trash-2"))
        self._btn_clean_old.setToolTip("Clean finished tasks")
        self._btn_clean_old.setAccessibleName("Clean finished tasks")
        self._btn_clean_old.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_clean_old.clicked.connect(self.clean_old_requested.emit)

        filters_layout.addWidget(self._filter_text, 1)
        filters_layout.addWidget(self._filter_environment)
        filters_layout.addWidget(self._filter_state)
        filters_layout.addWidget(clear_filters, 0, Qt.AlignRight)
        filters_layout.addWidget(self._btn_clean_old, 0, Qt.AlignRight)

        columns = QWidget()
        columns_layout = QHBoxLayout(columns)
        columns_layout.setContentsMargins(12, 0, 12, 0)
        columns_layout.setSpacing(12)
        c1 = QLabel("Task")
        c1.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c2 = QLabel("State")
        c2.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c3 = QLabel("Info")
        c3.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c1.setMinimumWidth(260)
        c2.setMinimumWidth(180)
        columns_layout.addWidget(c1, 5)
        columns_layout.addWidget(c2, 0)
        columns_layout.addWidget(c3, 4)
        columns_layout.addSpacing(self._btn_clean_old.sizeHint().width())

        self._tabs = QTabBar()
        self._tabs.setObjectName("DashboardTabs")
        self._tabs.setDocumentMode(True)
        self._tabs.setExpanding(True)
        self._tabs.addTab("Active Tasks")
        self._tabs.addTab("Past Tasks")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        tabs_row = QWidget()
        tabs_row_layout = QHBoxLayout(tabs_row)
        tabs_row_layout.setContentsMargins(0, 0, 0, 0)
        tabs_row_layout.setSpacing(0)
        tabs_row_layout.addWidget(self._tabs, 1)

        pane = QFrame()
        pane.setObjectName("TaskTabPane")
        pane.setAttribute(Qt.WA_StyledBackground, True)
        pane_layout = QVBoxLayout(pane)
        pane_layout.setContentsMargins(0, 8, 0, 0)
        pane_layout.setSpacing(10)

        self._stack = QStackedWidget()

        active_page = QWidget()
        active_layout = QVBoxLayout(active_page)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(0)

        self._scroll_active = QScrollArea()
        self._scroll_active.setWidgetResizable(True)
        self._scroll_active.setFrameShape(QScrollArea.NoFrame)
        self._scroll_active.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_active.setObjectName("TaskScroll")

        self._list_active = QWidget()
        self._list_active.setObjectName("TaskList")
        self._list_layout_active = QVBoxLayout(self._list_active)
        self._list_layout_active.setContentsMargins(12, 8, 12, 8)
        self._list_layout_active.setSpacing(6)
        self._list_layout_active.addStretch(1)
        self._scroll_active.setWidget(self._list_active)
        active_layout.addWidget(self._scroll_active, 1)

        past_page = QWidget()
        past_layout = QVBoxLayout(past_page)
        past_layout.setContentsMargins(0, 0, 0, 0)
        past_layout.setSpacing(10)

        self._scroll_past = QScrollArea()
        self._scroll_past.setWidgetResizable(True)
        self._scroll_past.setFrameShape(QScrollArea.NoFrame)
        self._scroll_past.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_past.setObjectName("TaskScroll")

        self._list_past = QWidget()
        self._list_past.setObjectName("TaskList")
        self._list_layout_past = QVBoxLayout(self._list_past)
        self._list_layout_past.setContentsMargins(12, 8, 12, 8)
        self._list_layout_past.setSpacing(6)
        self._list_layout_past.addStretch(1)
        self._scroll_past.setWidget(self._list_past)

        self._past_loading_indicator = QLabel("Loading more tasks...")
        self._past_loading_indicator.setStyleSheet(
            "color: rgba(237, 239, 245, 150); font-size: 11px; padding: 8px;"
        )
        self._past_loading_indicator.hide()

        past_layout.addWidget(self._scroll_past, 1)
        past_layout.addWidget(self._past_loading_indicator, 0, Qt.AlignCenter)

        self._stack.addWidget(active_page)
        self._stack.addWidget(past_page)

        pane_layout.addWidget(filters)
        pane_layout.addWidget(columns)
        pane_layout.addWidget(self._stack, 1)

        table_layout.addWidget(tabs_row, 0)
        table_layout.addWidget(pane, 1)
        layout.addWidget(table, 1)

        self._rows_active: dict[str, TaskRow] = {}
        self._rows_past: dict[str, TaskRow] = {}

        # Initialize animator after widgets are created
        self._past_animator = PastTaskAnimator(
            self._scroll_past,
            lambda: self._rows_past,
            parent=self
        )

        # Initialize progressive loader
        self._past_loader = PastTaskProgressiveLoader(
            load_callback=self._request_load_batch,
            indicator_callback=self._set_loading_indicator_visible,
            parent=self,  # Add parent for proper Qt lifecycle
        )

    def hideEvent(self, event: QHideEvent) -> None:
        self._past_animator.cancel_entrances()
        self._past_loader.cancel()
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._stack.currentIndex() == 1:
            self._past_animator.on_tab_shown()

    def _set_selected_task_id(self, task_id: str | None) -> None:
        task_id = str(task_id or "").strip() or None
        if self._selected_task_id == task_id:
            return
        prev = self._selected_task_id
        self._selected_task_id = task_id

        for rows in (self._rows_active, self._rows_past):
            if prev and prev in rows:
                rows[prev].set_selected(False)
            if task_id and task_id in rows:
                rows[task_id].set_selected(True)

    def _pick_new_row_stain(self, layout: QVBoxLayout) -> str:
        stains = tuple(stain for stain in ALLOWED_STAINS if stain != "slate")
        if not stains:
            stains = ("slate",)
        current: str | None = None
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if isinstance(widget, TaskRow):
                current = str(widget.property("stain") or "")
                break
        if current in stains:
            return stains[(stains.index(current) + 1) % len(stains)]
        return stains[0]

    def upsert_task(
        self, task: Task, stain: str | None = None, spinner_color: QColor | None = None
    ) -> None:
        row = self._rows_active.get(task.task_id)
        if row is None:
            row = TaskRow()
            row.set_task_id(task.task_id)
            row.set_stain(stain or self._pick_new_row_stain(self._list_layout_active))
            row.clicked.connect(self._on_row_clicked)
            row.discard_requested.connect(self.task_discard_requested.emit)
            self._rows_active[task.task_id] = row
            self._list_layout_active.insertWidget(0, row)
        elif stain:
            row.set_stain(stain)

        row.set_selected(self._selected_task_id == task.task_id)
        row.update_from_task(task, spinner_color=spinner_color)
        row.setVisible(self._row_visible_for_task(task))

    def upsert_past_task(self, task: Task, stain: str | None = None) -> None:
        row = self._rows_past.get(task.task_id)
        created = False
        if row is None:
            row = TaskRow(discard_enabled=False)
            row.set_task_id(task.task_id)
            row.set_stain(stain or self._pick_new_row_stain(self._list_layout_past))
            row.clicked.connect(self._on_row_clicked)
            self._rows_past[task.task_id] = row
            self._list_layout_past.insertWidget(
                max(0, self._list_layout_past.count() - 1), row
            )
            created = True
        elif stain:
            row.set_stain(stain)

        row.set_selected(self._selected_task_id == task.task_id)
        row.update_from_task(task)
        row.setVisible(self._row_visible_for_task(task))
        if created and self._stack.currentIndex() == 1:
            self._past_animator.on_past_task_added()

    def set_environment_filter_options(self, envs: list[tuple[str, str]]) -> None:
        current = str(self._filter_environment.currentData() or "")
        self._filter_environment.blockSignals(True)
        try:
            self._filter_environment.clear()
            self._filter_environment.addItem("All environments", "")
            for env_id, label in envs:
                self._filter_environment.addItem(label or env_id, env_id)
            idx = self._filter_environment.findData(current)
            if idx < 0:
                idx = 0
            self._filter_environment.setCurrentIndex(idx)
        finally:
            self._filter_environment.blockSignals(False)
        self._apply_filters()

    def _clear_filters(self) -> None:
        self._filter_text.setText("")
        self._filter_environment.setCurrentIndex(0)
        self._filter_state.setCurrentIndex(0)

    def _on_filter_changed(self, _value: object = None) -> None:
        raw = (self._filter_text.text() or "").strip().lower()
        self._filter_text_tokens = [t for t in raw.split() if t]
        self._apply_filters()

    def _task_matches_text(self, task: Task) -> bool:
        if not self._filter_text_tokens:
            return True
        haystack = " ".join(
            [
                str(task.task_id or ""),
                str(task.environment_id or ""),
                str(task.status or ""),
                task.prompt_one_line(),
                task.info_one_line(),
            ]
        ).lower()
        return all(token in haystack for token in self._filter_text_tokens)

    @staticmethod
    def _task_matches_state(task: Task, state: str) -> bool:
        state = str(state or "any")
        if state == "any":
            return True
        if state == "active":
            return task.is_active()
        status = (task.status or "").lower()
        if state == "done":
            return task.is_done() or (status == "exited" and task.exit_code == 0)
        if state == "failed":
            if task.is_failed():
                return True
            return task.exit_code is not None and task.exit_code != 0
        return True

    def _row_visible_for_task(self, task: Task) -> bool:
        env_filter = str(self._filter_environment.currentData() or "")
        if env_filter and str(task.environment_id or "") != env_filter:
            return False
        state_filter = str(self._filter_state.currentData() or "any")
        if not self._task_matches_state(task, state_filter):
            return False
        return self._task_matches_text(task)

    def _apply_filters(self) -> None:
        for rows in (self._rows_active, self._rows_past):
            for row in rows.values():
                task = row.last_task()
                row.setVisible(
                    True if task is None else self._row_visible_for_task(task)
                )

    def _on_row_clicked(self) -> None:
        row = self.sender()
        if isinstance(row, TaskRow) and row.task_id:
            self._set_selected_task_id(row.task_id)
            self.task_selected.emit(row.task_id)

    def remove_tasks(self, task_ids: set[str]) -> None:
        for rows in (self._rows_active, self._rows_past):
            for task_id in task_ids:
                row = rows.pop(task_id, None)
                if row is not None:
                    row.setParent(None)
                    row.deleteLater()
                if self._selected_task_id == task_id:
                    self._selected_task_id = None

    def _request_load_batch(self, offset: int, limit: int) -> int:
        """Request loading a batch of past tasks.
        
        This is called by the progressive loader. It calls the callback
        that the main window provides.
        
        Args:
            offset: Starting offset for loading.
            limit: Maximum number of tasks to load.
            
        Returns:
            Number of tasks actually loaded.
        """
        if self._load_past_batch_callback is not None:
            return self._load_past_batch_callback(offset, limit)
        return 0

    def _set_loading_indicator_visible(self, visible: bool) -> None:
        """Show or hide the loading indicator.
        
        Args:
            visible: True to show indicator, False to hide.
        """
        self._past_loading_indicator.setVisible(visible)

    def _on_tab_changed(self, index: int) -> None:
        if index >= 0:
            self._stack.setCurrentIndex(index)
        
        # Always cancel any active loader when switching tabs
        if index != 1:
            self._past_animator.cancel_entrances()
            self._past_loader.cancel()
            return
        
        # Cancel any existing loader before starting new one
        self._past_loader.cancel()
        
        # Start progressive loading
        # Check if we need to load OR if loading was interrupted
        if not self._rows_past or self._past_loader.has_more():
            self._past_loader.start()
        
        self._past_animator.on_tab_shown()
