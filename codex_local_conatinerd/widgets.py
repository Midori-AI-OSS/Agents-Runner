import math

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QSyntaxHighlighter
from PySide6.QtGui import QTextCharFormat
from PySide6.QtGui import QTextDocument
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


class BouncingLoadingBar(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 72,
        height: int = 8,
        chunk_fraction: float = 0.20,
    ) -> None:
        super().__init__(parent)
        self._chunk_fraction = float(chunk_fraction)
        self._offset = 0.0
        self._direction = 1.0
        self._color = QColor(148, 163, 184, 220)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(int(width), int(height))

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def _tick(self) -> None:
        rect = self.rect().adjusted(1, 1, -1, -1)
        chunk_w = max(2, int(rect.width() * self._chunk_fraction))
        max_offset = max(0.0, float(rect.width() - chunk_w))
        speed = max(1.0, rect.width() * 0.035)

        self._offset += self._direction * speed
        if self._offset <= 0.0:
            self._offset = 0.0
            self._direction = 1.0
        elif self._offset >= max_offset:
            self._offset = max_offset
            self._direction = -1.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        outer = self.rect().adjusted(0, 0, -1, -1)
        inner = outer.adjusted(1, 1, -1, -1)
        if inner.width() <= 0 or inner.height() <= 0:
            return

        border = QColor(255, 255, 255, 22)
        bg = QColor(self._color.red(), self._color.green(), self._color.blue(), 22)
        chunk = QColor(self._color.red(), self._color.green(), self._color.blue(), 215)

        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRect(inner)

        painter.setPen(border)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(outer)

        chunk_w = max(2, int(inner.width() * self._chunk_fraction))
        max_offset = max(0.0, float(inner.width() - chunk_w))
        x = int(inner.left() + (0.0 if max_offset <= 0.0 else self._offset))
        painter.setPen(Qt.NoPen)
        painter.setBrush(chunk)
        painter.drawRect(x, int(inner.top()), int(chunk_w), int(inner.height()))


class StatusGlyph(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 18) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self._mode = "idle"
        self._color = QColor(148, 163, 184, 220)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)

    def set_mode(self, mode: str, color: QColor | None = None) -> None:
        self._mode = mode
        if color is not None:
            self._color = color
        if mode == "spinner":
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 7.0) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        center = rect.center()
        size = min(rect.width(), rect.height())
        ring_r = size * 0.36

        if self._mode == "spinner":
            for i in range(12):
                t = (i / 12.0) * math.tau
                angle_deg = math.degrees(t) + self._angle
                alpha = int(30 + (i / 12.0) * 200)
                color = QColor(self._color.red(), self._color.green(), self._color.blue(), alpha)
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)

                x = center.x() + math.cos(math.radians(angle_deg)) * ring_r
                y = center.y() + math.sin(math.radians(angle_deg)) * ring_r
                r = max(2.0, size * 0.14)
                painter.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))
            return

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color.red(), self._color.green(), self._color.blue(), 45))
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

        pen = painter.pen()
        pen.setWidthF(max(1.6, size * 0.12))
        pen.setColor(QColor(self._color.red(), self._color.green(), self._color.blue(), 220))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        if self._mode == "check":
            path = QPainterPath()
            path.moveTo(rect.left() + size * 0.28, rect.top() + size * 0.55)
            path.lineTo(rect.left() + size * 0.44, rect.top() + size * 0.70)
            path.lineTo(rect.left() + size * 0.74, rect.top() + size * 0.34)
            painter.drawPath(path)
            return

        if self._mode == "x":
            painter.drawLine(
                int(rect.left() + size * 0.30),
                int(rect.top() + size * 0.30),
                int(rect.left() + size * 0.70),
                int(rect.top() + size * 0.70),
            )
            painter.drawLine(
                int(rect.left() + size * 0.70),
                int(rect.top() + size * 0.30),
                int(rect.left() + size * 0.30),
                int(rect.top() + size * 0.70),
            )
            return


class LogHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

        def fmt(color: QColor, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(color)
            if bold:
                f.setFontWeight(700)
            return f

        def fmt_block(
            foreground: QColor,
            *,
            background: QColor | None = None,
            bold: bool = False,
            italic: bool = False,
        ) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(foreground)
            if background is not None:
                f.setBackground(background)
            if bold:
                f.setFontWeight(700)
            if italic:
                f.setFontItalic(True)
            return f

        slate = QColor(148, 163, 184, 235)
        cyan = QColor(56, 189, 248, 235)
        emerald = QColor(16, 185, 129, 235)
        rose = QColor(244, 63, 94, 235)
        amber = QColor(245, 158, 11, 235)
        violet = QColor(168, 85, 247, 235)
        zinc = QColor(226, 232, 240, 235)

        self._rules: list[tuple[object, QTextCharFormat]] = [
            (r"\[host\]", fmt(cyan, True)),
            (r"\[preflight\]", fmt(emerald, True)),
            (r"\bpull complete\b", fmt(emerald, True)),
            (r"\bdocker pull\b", fmt(cyan, True)),
            (r"\b(exit|exited)\b", fmt(amber, True)),
            (r"\b(error|failed|fatal|exception)\b", fmt(rose, True)),
            # Markdown-ish extras (syntax highlighting, not rich-text rendering).
            (r"^#{1,6}\s+.*$", fmt(zinc, True)),
            (r"^\s*(?:[-*+]|\d+\.)\s+", fmt(amber, True)),
            (r"^\s*>\s+.*$", fmt(slate, False)),
            (r"\*\*[^*]+\*\*", fmt(zinc, True)),
            (r"__[^_]+__", fmt(zinc, True)),
            (r"`[^`]+`", fmt_block(violet, background=QColor(168, 85, 247, 28))),
            (r"```.*$", fmt_block(violet, background=QColor(168, 85, 247, 28), bold=True)),
            (r"https?://\S+", fmt(cyan, False)),
            (r"\bTODO\b", fmt(amber, True)),
            (r"\bNOTE\b", fmt(slate, True)),
        ]

    def highlightBlock(self, text: str) -> None:
        import re

        in_fence = self.previousBlockState() == 1
        fence_line = bool(re.match(r"^```", text))
        if fence_line:
            self.setCurrentBlockState(0 if in_fence else 1)
        else:
            self.setCurrentBlockState(1 if in_fence else 0)

        if in_fence and not fence_line:
            code_format = QTextCharFormat()
            code_format.setForeground(QColor(226, 232, 240, 215))
            code_format.setBackground(QColor(15, 23, 42, 90))
            self.setFormat(0, len(text), code_format)
            return

        for pattern, style in self._rules:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), style)
