from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.ui.task_model import Task
from agents_runner.ui.task_model import _task_display_status
from agents_runner.ui.utils import _format_duration
from agents_runner.ui.utils import _rgba
from agents_runner.ui.utils import _stain_color
from agents_runner.ui.utils import _status_color
from agents_runner.widgets import BouncingLoadingBar
from agents_runner.widgets import GlassCard
from agents_runner.widgets import StatusGlyph


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setWordWrap(False)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def setFullText(self, text: str) -> None:
        self._full_text = text
        self._update_elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.ElideRight, max(10, self.width() - 4))
        super().setText(elided)


class TaskRow(QWidget):
    clicked = Signal()
    discard_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._task_id: str | None = None
        self._last_task: Task | None = None
        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self._task = ElidedLabel("—")
        self._task.setStyleSheet("font-weight: 650; color: rgba(237, 239, 245, 235);")
        self._task.setMinimumWidth(260)
        self._task.setTextInteractionFlags(Qt.NoTextInteraction)
        self._task.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        state_wrap = QWidget()
        state_layout = QHBoxLayout(state_wrap)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(8)
        self._glyph = StatusGlyph(size=18)
        self._glyph.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._busy_bar = BouncingLoadingBar(width=72, height=8)
        self._busy_bar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._busy_bar.hide()
        self._status = QLabel("idle")
        self._status.setStyleSheet("color: rgba(237, 239, 245, 190);")
        self._status.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        state_layout.addWidget(self._glyph, 0, Qt.AlignLeft)
        state_layout.addWidget(self._busy_bar, 0, Qt.AlignLeft)
        state_layout.addWidget(self._status, 0, Qt.AlignLeft)
        state_wrap.setMinimumWidth(180)
        state_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._info = ElidedLabel("")
        self._info.setStyleSheet("color: rgba(237, 239, 245, 150);")
        self._info.setTextInteractionFlags(Qt.NoTextInteraction)
        self._info.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._btn_discard = QToolButton()
        self._btn_discard.setObjectName("RowTrash")
        self._btn_discard.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self._btn_discard.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_discard.setToolTip("Discard task")
        self._btn_discard.setCursor(Qt.PointingHandCursor)
        self._btn_discard.setIconSize(self._btn_discard.iconSize().expandedTo(self._glyph.size()))
        self._btn_discard.clicked.connect(self._on_discard_clicked)

        layout.addWidget(self._task, 5)
        layout.addWidget(state_wrap, 0)
        layout.addWidget(self._info, 4)
        layout.addWidget(self._btn_discard, 0, Qt.AlignRight)

        self.setCursor(Qt.PointingHandCursor)
        self.set_stain("slate")

    @property
    def task_id(self) -> str | None:
        return self._task_id

    def set_task_id(self, task_id: str) -> None:
        self._task_id = task_id

    def _on_discard_clicked(self) -> None:
        if self._task_id:
            self.discard_requested.emit(self._task_id)

    def set_stain(self, stain: str) -> None:
        if (self.property("stain") or "") == stain:
            return
        self.setProperty("stain", stain)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_selected(self, selected: bool) -> None:
        selected = bool(selected)
        if bool(self.property("selected")) == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_task(self, text: str) -> None:
        self._task.setFullText(text)

    def set_info(self, text: str) -> None:
        self._info.setFullText(text)

    def update_from_task(self, task: Task, spinner_color: QColor | None = None) -> None:
        self._last_task = task
        self.set_task(task.prompt_one_line())
        self.set_info(task.info_one_line())

        display = _task_display_status(task)
        status_key = (task.status or "").lower()
        if task.is_done():
            color = _status_color("done")
        elif task.is_failed() or (task.exit_code is not None and task.exit_code != 0):
            color = _status_color("failed")
        else:
            color = _status_color(status_key)
        self._status.setText(display)
        self._status.setStyleSheet(f"color: {_rgba(color, 235)}; font-weight: 700;")

        if task.is_active():
            self._glyph.hide()
            self._busy_bar.set_color(spinner_color or color)
            self._busy_bar.set_mode("dotted" if status_key == "queued" else "bounce")
            self._busy_bar.show()
            self._busy_bar.start()
            return
        self._busy_bar.stop()
        self._busy_bar.hide()
        self._glyph.show()
        if task.is_done():
            self._glyph.set_mode("check", color)
            return
        if task.is_failed() or (task.exit_code is not None and task.exit_code != 0):
            self._glyph.set_mode("x", color)
            return
        self._glyph.set_mode("idle", color)

    def last_task(self) -> Task | None:
        return self._last_task


class DashboardPage(QWidget):
    task_selected = Signal(str)
    clean_old_requested = Signal()
    task_discard_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_task_id: str | None = None
        self._filter_text_tokens: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        table = GlassCard()
        table_layout = QVBoxLayout(table)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)

        filters = QWidget()
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(8, 0, 8, 0)
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
        clear_filters.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        clear_filters.setToolButtonStyle(Qt.ToolButtonIconOnly)
        clear_filters.setToolTip("Clear filters")
        clear_filters.setAccessibleName("Clear filters")
        clear_filters.clicked.connect(self._clear_filters)

        self._btn_clean_old = QToolButton()
        self._btn_clean_old.setObjectName("RowTrash")
        self._btn_clean_old.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
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
        columns_layout.setContentsMargins(8, 0, 8, 0)
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

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setObjectName("TaskScroll")

        self._list = QWidget()
        self._list.setObjectName("TaskList")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list)

        table_layout.addWidget(filters)
        table_layout.addWidget(columns)
        table_layout.addWidget(self._scroll, 1)
        layout.addWidget(table, 1)

        self._rows: dict[str, TaskRow] = {}

    def _set_selected_task_id(self, task_id: str | None) -> None:
        task_id = str(task_id or "").strip() or None
        if self._selected_task_id == task_id:
            return
        prev = self._selected_task_id
        self._selected_task_id = task_id

        if prev and prev in self._rows:
            self._rows[prev].set_selected(False)
        if task_id and task_id in self._rows:
            self._rows[task_id].set_selected(True)

    def _pick_new_row_stain(self) -> str:
        stains = tuple(stain for stain in ALLOWED_STAINS if stain != "slate")
        if not stains:
            stains = ("slate",)
        current: str | None = None
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if isinstance(widget, TaskRow):
                current = str(widget.property("stain") or "")
                break
        if current in stains:
            return stains[(stains.index(current) + 1) % len(stains)]
        return stains[0]

    def upsert_task(self, task: Task, stain: str | None = None, spinner_color: QColor | None = None) -> None:
        row = self._rows.get(task.task_id)
        if row is None:
            row = TaskRow()
            row.set_task_id(task.task_id)
            row.set_stain(stain or self._pick_new_row_stain())
            row.clicked.connect(self._on_row_clicked)
            row.discard_requested.connect(self.task_discard_requested.emit)
            self._rows[task.task_id] = row
            self._list_layout.insertWidget(0, row)
        elif stain:
            row.set_stain(stain)

        row.set_selected(self._selected_task_id == task.task_id)
        row.update_from_task(task, spinner_color=spinner_color)
        row.setVisible(self._row_visible_for_task(task))

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
        for row in self._rows.values():
            task = row.last_task()
            row.setVisible(True if task is None else self._row_visible_for_task(task))

    def _on_row_clicked(self) -> None:
        row = self.sender()
        if isinstance(row, TaskRow) and row.task_id:
            self._set_selected_task_id(row.task_id)
            self.task_selected.emit(row.task_id)

    def remove_tasks(self, task_ids: set[str]) -> None:
        for task_id in task_ids:
            row = self._rows.pop(task_id, None)
            if row is not None:
                row.setParent(None)
                row.deleteLater()
            if self._selected_task_id == task_id:
                self._selected_task_id = None
