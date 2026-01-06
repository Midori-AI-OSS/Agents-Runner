from __future__ import annotations

from PySide6.QtCore import Property
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QParallelAnimationGroup
from PySide6.QtCore import QPoint
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import QRect
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
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QTabBar
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QGraphicsOpacityEffect

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.ui.task_model import Task
from agents_runner.ui.task_model import _task_display_status
from agents_runner.ui.utils import _format_duration
from agents_runner.ui.utils import _rgba
from agents_runner.ui.utils import _stain_color
from agents_runner.ui.utils import _status_color
from agents_runner.widgets import BouncingLoadingBar
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

    def __init__(self, parent: QWidget | None = None, *, discard_enabled: bool = True) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._task_id: str | None = None
        self._last_task: Task | None = None
        self._content_offset = 0.0
        self._entrance_anim: QParallelAnimationGroup | None = None
        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("selected", False)

        self._content = QWidget(self)

        layout = QHBoxLayout(self._content)
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
        self._btn_discard.setVisible(bool(discard_enabled))
        self._btn_discard.setEnabled(bool(discard_enabled))

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

    def _apply_content_geometry(self) -> None:
        self._content.setGeometry(self.rect().translated(int(self._content_offset), 0))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_content_geometry()

    def _get_content_offset(self) -> float:
        return float(self._content_offset)

    def _set_content_offset(self, value: float) -> None:
        value = float(value)
        if self._content_offset == value:
            return
        self._content_offset = value
        self._apply_content_geometry()

    contentOffset = Property(float, _get_content_offset, _set_content_offset)

    def prepare_entrance(self, *, distance: int = 36) -> None:
        effect = self.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        self._set_content_offset(float(distance))

    def play_entrance(
        self,
        *,
        distance: int = 36,
        fade_ms: int = 130,
        move_ms: int = 230,
        delay_ms: int = 0,
    ) -> None:
        if self._entrance_anim is not None:
            self._entrance_anim.stop()
            self._entrance_anim = None

        def _start() -> None:
            self.prepare_entrance(distance=distance)

            effect = self.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                return

            fade_anim = QPropertyAnimation(effect, b"opacity", self)
            fade_anim.setDuration(int(max(0, fade_ms)))
            fade_anim.setStartValue(0.0)
            fade_anim.setEndValue(1.0)
            fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            slide_anim = QPropertyAnimation(self, b"contentOffset", self)
            slide_anim.setDuration(int(max(0, move_ms)))
            slide_anim.setStartValue(float(distance))
            slide_anim.setEndValue(0.0)
            slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            group = QParallelAnimationGroup(self)
            group.addAnimation(fade_anim)
            group.addAnimation(slide_anim)
            group.finished.connect(self._on_entrance_finished)
            self._entrance_anim = group
            group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        if delay_ms > 0:
            QTimer.singleShot(int(delay_ms), _start)
        else:
            _start()

    def _on_entrance_finished(self) -> None:
        self._entrance_anim = None
        self._set_content_offset(0.0)
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)
            # Avoid stacking opacity effects (page transitions also use them) which can
            # cause odd painting/layout behavior when navigating.
            self.setGraphicsEffect(None)

    def cancel_entrance(self) -> None:
        if self._entrance_anim is not None:
            self._entrance_anim.stop()
            self._entrance_anim = None
        self._on_entrance_finished()

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
    past_load_more_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_task_id: str | None = None
        self._filter_text_tokens: list[str] = []
        self._past_entrance_queue: list[TaskRow] = []
        self._past_entrance_seen: set[str] = set()
        self._past_entrance_timer = QTimer(self)
        self._past_entrance_timer.setSingleShot(True)
        self._past_entrance_timer.timeout.connect(self._play_next_past_entrance)
        self._past_visible_scan_reset_pending = False
        self._past_visible_scan_timer = QTimer(self)
        self._past_visible_scan_timer.setSingleShot(True)
        self._past_visible_scan_timer.timeout.connect(self._queue_visible_past_entrances)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        table = QWidget()
        table_layout = QVBoxLayout(table)
        table_layout.setContentsMargins(0, 12, 0, 12)
        table_layout.setSpacing(0)

        filters = QWidget()
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)
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
        columns_layout.setContentsMargins(0, 0, 0, 0)
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
        self._list_layout_active.setContentsMargins(8, 8, 8, 8)
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
        self._list_layout_past.setContentsMargins(8, 8, 8, 8)
        self._list_layout_past.setSpacing(6)
        self._list_layout_past.addStretch(1)
        self._scroll_past.setWidget(self._list_past)

        self._btn_load_more = QPushButton("Load more")
        self._btn_load_more.setCursor(Qt.PointingHandCursor)
        self._btn_load_more.clicked.connect(self._request_more_past_tasks)

        self._scroll_past.verticalScrollBar().valueChanged.connect(self._on_past_scroll_value_changed)

        past_layout.addWidget(self._scroll_past, 1)
        past_layout.addWidget(self._btn_load_more, 0, Qt.AlignRight)

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

    def _cancel_past_entrances(self) -> None:
        self._past_visible_scan_timer.stop()
        self._past_visible_scan_reset_pending = False

        self._past_entrance_timer.stop()
        self._past_entrance_queue.clear()

        for row in self._rows_past.values():
            row.cancel_entrance()

    def hideEvent(self, event) -> None:
        self._cancel_past_entrances()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._stack.currentIndex() == 1:
            self._schedule_visible_past_entrances(reset=False, delay_ms=0)

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

    def upsert_task(self, task: Task, stain: str | None = None, spinner_color: QColor | None = None) -> None:
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
            self._list_layout_past.insertWidget(max(0, self._list_layout_past.count() - 1), row)
            created = True
        elif stain:
            row.set_stain(stain)

        row.set_selected(self._selected_task_id == task.task_id)
        row.update_from_task(task)
        row.setVisible(self._row_visible_for_task(task))
        if created and self._stack.currentIndex() == 1:
            self._schedule_visible_past_entrances(reset=False, delay_ms=0)

    def _queue_past_entrance(self, row: TaskRow) -> bool:
        if row in self._past_entrance_queue:
            return False
        if row.task_id:
            self._past_entrance_seen.add(row.task_id)
        row.prepare_entrance(distance=36)
        self._past_entrance_queue.append(row)
        if not self._past_entrance_timer.isActive():
            self._past_entrance_timer.start(0)
        return True

    def _past_row_intersects_viewport(self, row: TaskRow) -> bool:
        if row.parent() is None or not row.isVisible():
            return False
        viewport = self._scroll_past.viewport()
        top_left = row.mapTo(viewport, QPoint(0, 0))
        rect = QRect(top_left, row.size())
        return viewport.rect().intersects(rect)

    def _past_rows_in_viewport(self) -> list[TaskRow]:
        rows: list[TaskRow] = []
        for row in self._rows_past.values():
            if self._past_row_intersects_viewport(row):
                rows.append(row)
        rows.sort(key=lambda r: r.y())
        return rows

    def _schedule_visible_past_entrances(self, *, reset: bool, delay_ms: int) -> None:
        if self._stack.currentIndex() != 1:
            return
        if reset:
            self._past_visible_scan_reset_pending = True
        self._past_visible_scan_timer.start(int(max(0, delay_ms)))

    def _queue_visible_past_entrances(self) -> None:
        if self._stack.currentIndex() != 1:
            return

        if self._past_visible_scan_reset_pending:
            self._past_visible_scan_reset_pending = False
            self._past_entrance_seen.clear()
            stale_queue = list(self._past_entrance_queue)
            self._past_entrance_queue.clear()
            self._past_entrance_timer.stop()
            for row in stale_queue:
                if row is None or row.parent() is None:
                    continue
                row.cancel_entrance()

        queued = 0
        for row in self._past_rows_in_viewport():
            if queued >= 14:
                break
            task_id = row.task_id
            if not task_id or task_id in self._past_entrance_seen:
                continue
            row.cancel_entrance()
            if self._queue_past_entrance(row):
                queued += 1

    def _on_past_scroll_value_changed(self, _value: int) -> None:
        self._schedule_visible_past_entrances(reset=False, delay_ms=35)

    def _play_next_past_entrance(self) -> None:
        while self._past_entrance_queue:
            row = self._past_entrance_queue.pop(0)
            if row is None or row.parent() is None:
                continue
            if not row.isVisible():
                row.cancel_entrance()
                continue
            row.play_entrance(distance=36, fade_ms=120, move_ms=220)
            break
        if self._past_entrance_queue:
            self._past_entrance_timer.start(65)

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
                row.setVisible(True if task is None else self._row_visible_for_task(task))

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

    def set_past_load_more_enabled(self, enabled: bool, label: str | None = None) -> None:
        self._btn_load_more.setEnabled(bool(enabled))
        if label is not None:
            self._btn_load_more.setText(str(label))
        elif enabled and self._btn_load_more.text() != "Load more":
            self._btn_load_more.setText("Load more")

    def _request_more_past_tasks(self) -> None:
        if not self._btn_load_more.isEnabled():
            return
        self._btn_load_more.setEnabled(False)
        self.past_load_more_requested.emit(len(self._rows_past))

    def _on_tab_changed(self, index: int) -> None:
        if index >= 0:
            self._stack.setCurrentIndex(index)
        if index != 1:
            self._cancel_past_entrances()
            return
        if not self._rows_past and self._btn_load_more.isEnabled():
            self._request_more_past_tasks()
        self._schedule_visible_past_entrances(reset=False, delay_ms=0)
