from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget

from agents_runner.ui.lucide_icons import lucide_icon


class BreadcrumbBar(QWidget):
    back_clicked = Signal()
    segment_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._back_btn = QToolButton()
        self._back_btn.setIcon(lucide_icon("arrow-left"))
        self._back_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setAutoRaise(True)
        self._back_btn.setStyleSheet("border-radius: 0px;")
        self._back_btn.clicked.connect(self.back_clicked.emit)

        self._segments_wrap = QWidget(self)
        self._segments_wrap.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._segments_layout = QHBoxLayout(self._segments_wrap)
        self._segments_layout.setContentsMargins(0, 0, 0, 0)
        self._segments_layout.setSpacing(2)

        self._ellipsis = QLabel("...")
        self._ellipsis.setStyleSheet("color: rgba(237, 239, 245, 160); font-size: 11px;")
        self._ellipsis.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._ellipsis.hide()

        self._segments_layout.addWidget(self._ellipsis)
        self._segment_buttons: list[QToolButton] = []

        layout.addWidget(self._back_btn, 0, Qt.AlignLeft)
        layout.addWidget(self._segments_wrap, 1)

    def set_segments(self, segments: list[tuple[str, str]]) -> None:
        for button in self._segment_buttons:
            self._segments_layout.removeWidget(button)
            button.deleteLater()
        self._segment_buttons.clear()

        for index, (label, path) in enumerate(segments):
            button = QToolButton()
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            button.setAutoRaise(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(
                "border-radius: 0px; color: rgba(237, 239, 245, 200); font-size: 11px; padding: 0px;"
            )
            text = label if index == 0 else f" / {label}"
            button.setText(text)
            button.clicked.connect(
                lambda checked=False, segment_path=path: self.segment_clicked.emit(
                    segment_path
                )
            )
            self._segments_layout.addWidget(button)
            self._segment_buttons.append(button)

        self._update_visible_segments()

    def set_back_enabled(self, enabled: bool) -> None:
        self._back_btn.setEnabled(enabled)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_visible_segments()

    def _update_visible_segments(self) -> None:
        if not self._segment_buttons:
            self._ellipsis.hide()
            return

        available = self._segments_wrap.width()
        if available <= 0:
            return

        spacing = self._segments_layout.spacing()
        widths = [button.sizeHint().width() for button in self._segment_buttons]
        ellipsis_width = self._ellipsis.sizeHint().width()

        start_index = 0
        for idx in range(len(widths)):
            count = len(widths) - idx
            width = sum(widths[idx:])
            if count > 1:
                width += spacing * (count - 1)
            if idx > 0:
                width += ellipsis_width + spacing
            if width <= available:
                start_index = idx
                break
        else:
            start_index = len(widths) - 1

        show_ellipsis = start_index > 0
        self._ellipsis.setVisible(show_ellipsis)

        for idx, button in enumerate(self._segment_buttons):
            button.setVisible(idx >= start_index)
