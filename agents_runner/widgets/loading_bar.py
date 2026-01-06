import math

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget
from typing import NamedTuple


class _DottedLine(NamedTuple):
    phase_offset: float
    duration_s: float
    alpha_scale: float
    width_scale: float


class BouncingLoadingBar(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 72,
        height: int = 8,
        chunk_fraction: float = 0.20,
    ) -> None:
        super().__init__(parent)
        self._mode = "bounce"
        self._chunk_fraction = float(chunk_fraction)
        self._offset = 0.0
        self._direction = 1.0
        self._phase = 0.0
        self._dotted_time_s = 0.0
        self._dotted_lines: list[_DottedLine] = []
        self._dotted_line_count = 0
        self._color = QColor(148, 163, 184, 220)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(int(width), int(height))

    def _ensure_dotted_lines(self, line_count: int) -> None:
        line_count = int(max(1, line_count))
        if line_count == self._dotted_line_count and self._dotted_lines:
            return

        base_duration_s = 1.15
        lines: list[_DottedLine] = []
        for i in range(line_count):
            # Deterministic "random-ish" variation (no RNG) so each line has its own
            # timing/feel instead of moving as a rigid group.
            f1 = (i * 0.61803398875) % 1.0
            f2 = (i * 0.41421356237) % 1.0
            f3 = (i * 0.73205080757) % 1.0

            phase_offset = f1
            duration_s = base_duration_s * (0.78 + 0.52 * f2)
            alpha_scale = 0.55 + 0.45 * f3
            width_scale = 0.85 + 0.30 * ((i * 0.27777777777) % 1.0)
            lines.append(
                _DottedLine(phase_offset, duration_s, alpha_scale, width_scale)
            )

        self._dotted_lines = lines
        self._dotted_line_count = line_count

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def set_mode(self, mode: str) -> None:
        mode = str(mode or "").strip().lower()
        if mode not in {"bounce", "pulse_full", "dotted"}:
            mode = "bounce"
        if self._mode == mode:
            return
        self._mode = mode
        if mode == "pulse_full":
            self._timer.setInterval(50)
        elif mode == "dotted":
            self._timer.setInterval(24)
            self._dotted_time_s = 0.0
            self._dotted_lines = []
            self._dotted_line_count = 0
        else:
            self._timer.setInterval(30)
        self.update()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def _tick(self) -> None:
        if self._mode == "pulse_full":
            self._phase = (self._phase + 0.08) % (math.tau * 4.0)
            self.update()
            return
        if self._mode == "dotted":
            dt_s = max(0.001, float(self._timer.interval()) / 1000.0)
            self._dotted_time_s += dt_s
            if self._dotted_time_s >= 3600.0:
                self._dotted_time_s %= 3600.0
            self.update()
            return

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

        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRect(inner)

        painter.setPen(border)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(outer)

        if self._mode == "pulse_full":
            pulse = 0.5 * (1.0 + math.sin(self._phase))
            alpha = int(110 + pulse * 105)
            chunk = QColor(
                self._color.red(), self._color.green(), self._color.blue(), alpha
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(chunk)
            painter.drawRect(inner)
            return

        if self._mode == "dotted":
            base_line_w = max(2, int(inner.height() * 0.32))
            base_gap = max(3, int(base_line_w * 1.9))
            line_count = max(4, min(9, inner.width() // max(1, base_line_w + base_gap)))
            self._ensure_dotted_lines(line_count)

            travel_margin = max(6.0, float(base_line_w) * 3.0)
            travel_w = float(inner.width()) + 2.0 * travel_margin

            r, g, b = self._color.red(), self._color.green(), self._color.blue()
            painter.setPen(Qt.NoPen)
            for line in self._dotted_lines:
                phase = (
                    self._dotted_time_s / max(0.25, line.duration_s) + line.phase_offset
                ) % 1.0
                eased = 0.5 - 0.5 * math.cos(math.pi * phase)
                fade = max(0.0, math.sin(math.pi * phase))

                x = float(inner.left()) - travel_margin + travel_w * eased
                line_w = max(2, int(base_line_w * line.width_scale))
                alpha = int((70 + 170 * line.alpha_scale) * fade)
                if alpha <= 0:
                    continue
                painter.setBrush(QColor(r, g, b, alpha))
                painter.drawRect(
                    int(x), int(inner.top()), int(line_w), int(inner.height())
                )
            return

        chunk = QColor(self._color.red(), self._color.green(), self._color.blue(), 215)
        chunk_w = max(2, int(inner.width() * self._chunk_fraction))
        max_offset = max(0.0, float(inner.width() - chunk_w))
        x = int(inner.left() + (0.0 if max_offset <= 0.0 else self._offset))
        painter.setPen(Qt.NoPen)
        painter.setBrush(chunk)
        painter.drawRect(x, int(inner.top()), int(chunk_w), int(inner.height()))
