from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent
from PySide6.QtWidgets import QCheckBox, QWidget


class AnimatedCheckBox(QCheckBox):
    """A checkbox with smooth animation when toggled."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._check_progress = 0.0
        self._animation: QPropertyAnimation | None = None
        self.stateChanged.connect(self._on_state_changed)

    def _on_state_changed(self, state: int) -> None:
        target = 1.0 if state == Qt.CheckState.Checked.value else 0.0

        if self._animation:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"check_progress")
        self._animation.setDuration(200)
        self._animation.setStartValue(self._check_progress)
        self._animation.setEndValue(target)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(lambda: self.update())
        self._animation.start()

    def get_check_progress(self) -> float:
        return self._check_progress

    def set_check_progress(self, value: float) -> None:
        self._check_progress = max(0.0, min(1.0, value))
        self.update()

    check_progress = property(get_check_progress, set_check_progress)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        if self._check_progress > 0.0 and self._check_progress < 1.0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            style_opt = self.style().subControlRect(
                self.style().CC_CheckBox,
                self.style().styleOption(self),
                self.style().SC_CheckBoxIndicator,
                self,
            )

            if style_opt.isValid():
                rect = style_opt.adjusted(4, 4, -4, -4)

                base_color = QColor(16, 185, 129)
                alpha = int(165 * self._check_progress)
                fill_color = QColor(
                    base_color.red(), base_color.green(), base_color.blue(), alpha
                )

                path = QPainterPath()
                path.addRect(rect)

                painter.fillPath(path, fill_color)
