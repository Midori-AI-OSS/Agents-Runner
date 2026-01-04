from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton, QToolButton, QWidget


class AnimatedPushButton(QPushButton):
    """QPushButton with hover scale animation."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._scale = 1.0
        self._hover_anim: QPropertyAnimation | None = None
        self._press_anim: QPropertyAnimation | None = None

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._animate_scale(1.02)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._animate_scale(1.0)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self._animate_scale(0.98)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self.underMouse():
            self._animate_scale(1.02)
        else:
            self._animate_scale(1.0)

    def _animate_scale(self, target: float) -> None:
        if self._hover_anim:
            self._hover_anim.stop()

        self._hover_anim = QPropertyAnimation(self, b"scale")
        self._hover_anim.setDuration(150)
        self._hover_anim.setStartValue(self._scale)
        self._hover_anim.setEndValue(target)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(lambda: self.update())
        self._hover_anim.start()

    def get_scale(self) -> float:
        return self._scale

    def set_scale(self, value: float) -> None:
        self._scale = value
        self.update()

    scale = property(get_scale, set_scale)

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(int(base.width() * self._scale), int(base.height() * self._scale))


class AnimatedToolButton(QToolButton):
    """QToolButton with subtle hover effects."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._glow_effect: QGraphicsOpacityEffect | None = None
        self._glow_anim: QPropertyAnimation | None = None

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._animate_glow(0.15)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._animate_glow(0.0)

    def _animate_glow(self, target: float) -> None:
        if not self._glow_effect:
            self._glow_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._glow_effect)

        if self._glow_anim:
            self._glow_anim.stop()

        self._glow_anim = QPropertyAnimation(self._glow_effect, b"opacity")
        self._glow_anim.setDuration(200)
        self._glow_anim.setStartValue(self._glow_effect.opacity())
        self._glow_anim.setEndValue(1.0)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._glow_anim.start()
