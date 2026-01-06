from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QWidget


class GlassCard(QFrame):
    def __init__(
        self, parent: QWidget | None = None, animate_entrance: bool = False
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._animate_entrance = animate_entrance
        self._entrance_shown = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._animate_entrance and not self._entrance_shown:
            self._entrance_shown = True
            QTimer.singleShot(10, self._play_entrance_animation)

    def _play_entrance_animation(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

        self._entrance_anim = anim

    def paintEvent(self, event) -> None:
        rect = self.rect().adjusted(1, 1, -1, -1)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.addRect(rect)

        painter.fillPath(path, QColor(18, 20, 28, 165))
        painter.setPen(QColor(255, 255, 255, 25))
        painter.drawPath(path)
