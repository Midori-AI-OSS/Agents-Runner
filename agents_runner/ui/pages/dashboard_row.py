"""Dashboard task row widget components.

This module contains the TaskRow widget and supporting components used to display
individual tasks in the dashboard. Extracted from dashboard.py to maintain the
600-line hard limit per file.
"""

from __future__ import annotations

from PySide6.QtCore import Property
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QParallelAnimationGroup
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtGui import QFontMetrics
from PySide6.QtGui import QMouseEvent
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QWidget

from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.task_model import Task
from agents_runner.ui.task_model import _task_display_status
from agents_runner.ui.utils import _rgba
from agents_runner.ui.utils import _status_color
from agents_runner.widgets import BouncingLoadingBar
from agents_runner.widgets import StatusGlyph


class ElidedLabel(QLabel):
    """Label that elides text with ellipsis when it doesn't fit."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setWordWrap(False)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def setFullText(self, text: str) -> None:
        """Set the full text, which will be elided if necessary."""
        self._full_text = text
        self._update_elide()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        """Update the displayed text with elision if necessary."""
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(
            self._full_text, Qt.ElideRight, max(10, self.width() - 4)
        )
        super().setText(elided)


class TaskRow(QWidget):
    """Widget representing a single task in the dashboard.

    Displays task information including name, status, and metadata. Supports
    entrance animations and selection state. Emits signals for user interactions.
    """

    clicked = Signal()
    discard_requested = Signal(str)
    attach_terminal_requested = Signal(str)

    def __init__(
        self, parent: QWidget | None = None, *, discard_enabled: bool = True
    ) -> None:
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
        self._btn_discard.setIcon(lucide_icon("trash-2"))
        self._btn_discard.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_discard.setToolTip("Discard task")
        self._btn_discard.setCursor(Qt.PointingHandCursor)
        self._btn_discard.setIconSize(
            self._btn_discard.iconSize().expandedTo(self._glyph.size())
        )
        self._btn_discard.clicked.connect(self._on_discard_clicked)
        self._btn_discard.setVisible(bool(discard_enabled))
        self._btn_discard.setEnabled(bool(discard_enabled))
        
        self._btn_attach = QToolButton()
        self._btn_attach.setObjectName("RowAttach")
        self._btn_attach.setIcon(lucide_icon("terminal"))
        self._btn_attach.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_attach.setToolTip("Attach Terminal")
        self._btn_attach.setCursor(Qt.PointingHandCursor)
        self._btn_attach.setIconSize(
            self._btn_attach.iconSize().expandedTo(self._glyph.size())
        )
        self._btn_attach.clicked.connect(self._on_attach_clicked)
        self._btn_attach.setVisible(False)  # Hidden by default

        layout.addWidget(self._task, 5)
        layout.addWidget(state_wrap, 0)
        layout.addWidget(self._info, 4)
        layout.addWidget(self._btn_attach, 0, Qt.AlignRight)
        layout.addWidget(self._btn_discard, 0, Qt.AlignRight)

        self.setCursor(Qt.PointingHandCursor)
        self.set_stain("slate")

    @property
    def task_id(self) -> str | None:
        """Get the task ID associated with this row."""
        return self._task_id

    def set_task_id(self, task_id: str) -> None:
        """Set the task ID for this row."""
        self._task_id = task_id

    def _apply_content_geometry(self) -> None:
        """Apply the current content offset to the content widget geometry."""
        self._content.setGeometry(self.rect().translated(int(self._content_offset), 0))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_content_geometry()

    def _get_content_offset(self) -> float:
        """Get the content offset for animation purposes."""
        return float(self._content_offset)

    def _set_content_offset(self, value: float) -> None:
        """Set the content offset for animation purposes."""
        value = float(value)
        if self._content_offset == value:
            return
        self._content_offset = value
        self._apply_content_geometry()

    contentOffset = Property(float, _get_content_offset, _set_content_offset)

    def prepare_entrance(self, *, distance: int = 36) -> None:
        """Prepare the row for entrance animation by setting initial state."""
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
        """Play the entrance animation for this row."""
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
        """Clean up after entrance animation completes."""
        self._entrance_anim = None
        self._set_content_offset(0.0)
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)
            # Avoid stacking opacity effects (page transitions also use them) which can
            # cause odd painting/layout behavior when navigating.
            self.setGraphicsEffect(None)

    def cancel_entrance(self) -> None:
        """Cancel any ongoing entrance animation."""
        if self._entrance_anim is not None:
            self._entrance_anim.stop()
            self._entrance_anim = None
        self._on_entrance_finished()

    def _on_discard_clicked(self) -> None:
        """Handle discard button click."""
        if self._task_id:
            self.discard_requested.emit(self._task_id)

    def set_stain(self, stain: str) -> None:
        """Set the color stain for this row (used for visual variety)."""
        if (self.property("stain") or "") == stain:
            return
        self.setProperty("stain", stain)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_selected(self, selected: bool) -> None:
        """Set the selection state of this row."""
        selected = bool(selected)
        if bool(self.property("selected")) == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_task(self, text: str) -> None:
        """Set the task name text."""
        self._task.setFullText(text)

    def set_info(self, text: str) -> None:
        """Set the task info text."""
        self._info.setFullText(text)

    def update_from_task(self, task: Task, spinner_color: QColor | None = None) -> None:
        """Update the row display based on task state."""
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
        """Get the last task object used to update this row."""
        return self._last_task
