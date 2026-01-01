from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QWidget


class GlassCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def paintEvent(self, event) -> None:
        rect = self.rect().adjusted(1, 1, -1, -1)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.addRect(rect)

        painter.fillPath(path, QColor(18, 20, 28, 165))
        painter.setPen(QColor(255, 255, 255, 25))
        painter.drawPath(path)
