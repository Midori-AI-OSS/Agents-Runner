from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QScrollArea, QWidget


class SmoothScrollArea(QScrollArea):
    """QScrollArea with smooth scrolling animation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scroll_anim: QPropertyAnimation | None = None

    def smooth_scroll_to(self, value: int, duration: int = 300) -> None:
        """Smoothly scroll to a specific vertical position."""
        scrollbar = self.verticalScrollBar()

        if self._scroll_anim:
            self._scroll_anim.stop()

        self._scroll_anim = QPropertyAnimation(scrollbar, b"value")
        self._scroll_anim.setDuration(duration)
        self._scroll_anim.setStartValue(scrollbar.value())
        self._scroll_anim.setEndValue(value)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.start()

    def smooth_scroll_by(self, delta: int, duration: int = 300) -> None:
        """Smoothly scroll by a delta amount."""
        scrollbar = self.verticalScrollBar()
        target = scrollbar.value() + delta
        self.smooth_scroll_to(target, duration)
