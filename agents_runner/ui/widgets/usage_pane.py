"""Usage pane widget for Settings: gh request totals plus a 60-minute per-minute line chart."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QFont
from PySide6.QtGui import QFontMetrics
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.gh.usage_counts import snapshot as snapshot_gh_usage

_BUCKET_COUNT = 60
_LEFT_MARGIN = 40
_RIGHT_MARGIN = 8
_TOP_MARGIN = 10
_BOTTOM_MARGIN = 20


class GhUsagePaneWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._total_value = QLabel("0")
        self._total_value.setStyleSheet("font-size: 15px; font-weight: 700;")
        self._chart = _UsageLineChart(self)

        total_row = QHBoxLayout()
        total_row.setContentsMargins(0, 0, 0, 0)
        total_row.setSpacing(8)
        total_row.addWidget(QLabel("Total requests"))
        total_row.addWidget(self._total_value)
        total_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(total_row)
        layout.addWidget(self._chart)
        self.refresh()

    def refresh(self) -> None:
        snap = snapshot_gh_usage()
        self._total_value.setText(str(snap.total))
        self._chart.set_buckets(list(snap.buckets))


class _UsageLineChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buckets = [0] * _BUCKET_COUNT
        self.setFixedHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_buckets(self, buckets: list[int]) -> None:
        self._buckets = [max(0, int(value)) for value in buckets]
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = self.rect().adjusted(0, 0, -1, -1)
        if outer.width() <= _LEFT_MARGIN + _RIGHT_MARGIN + 2 or outer.height() <= _TOP_MARGIN + _BOTTOM_MARGIN + 2:
            return

        painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.drawRect(outer)

        plot = outer.adjusted(_LEFT_MARGIN, _TOP_MARGIN, -_RIGHT_MARGIN, -_BOTTOM_MARGIN)
        buckets = self._buckets or [0]
        y_max = max(1, max(buckets))

        font = QFont(self.font())
        font.setPointSize(max(7, font.pointSize() - 1))
        painter.setFont(font)
        metrics = QFontMetrics(font)

        painter.setPen(QPen(QColor(148, 163, 184, 60), 1.0))
        for frac in (0.0, 0.5, 1.0):
            y = plot.bottom() - int(round(frac * plot.height()))
            painter.drawLine(plot.left(), y, plot.right() + 1, y)

        painter.setPen(QColor(148, 163, 184, 210))
        max_label = str(y_max)
        painter.drawText(
            plot.left() - metrics.horizontalAdvance(max_label) - 5, plot.top() + metrics.ascent(), max_label
        )
        painter.drawText(plot.left() - metrics.horizontalAdvance("0") - 5, plot.bottom(), "0")
        painter.drawText(plot.left(), plot.bottom() + metrics.ascent() + 3, "-60m")
        painter.drawText(plot.right() - metrics.horizontalAdvance("now"), plot.bottom() + metrics.ascent() + 3, "now")

        step_x = plot.width() / max(1, len(buckets) - 1)
        points = [
            (plot.left() + step_x * index, plot.bottom() - (value / y_max) * plot.height())
            for index, value in enumerate(buckets)
        ]

        accent = QColor(56, 189, 248, 235)
        painter.setPen(QPen(accent, 2.0))
        for start, end in zip(points, points[1:]):
            painter.drawLine(int(round(start[0])), int(round(start[1])), int(round(end[0])), int(round(end[1])))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        for (x, y), value in zip(points, buckets):
            if value <= 0:
                continue
            painter.drawRect(int(round(x)) - 2, int(round(y)) - 2, 4, 4)
