import math

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget


class ArcSpinner(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 44) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 6.0) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        center = self.rect().center()
        ring_r = min(self.width(), self.height()) * 0.36

        for i in range(12):
            t = (i / 12.0) * math.tau
            angle_deg = math.degrees(t) + self._angle
            alpha = int(22 + (i / 12.0) * 190)

            color = QColor(56, 189, 248, alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)

            x = center.x() + math.cos(math.radians(angle_deg)) * ring_r
            y = center.y() + math.sin(math.radians(angle_deg)) * ring_r
            r = 3.4
            painter.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))
