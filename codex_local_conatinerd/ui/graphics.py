from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QRadialGradient
from PySide6.QtWidgets import QWidget


class _EnvironmentTintOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None, alpha: int = 13) -> None:
        super().__init__(parent)
        self._alpha = int(min(max(alpha, 0), 255))
        self._color = QColor(0, 0, 0, 0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def set_tint_color(self, color: QColor | None) -> None:
        if color is None:
            self._color = QColor(0, 0, 0, 0)
        else:
            self._color = QColor(color.red(), color.green(), color.blue(), self._alpha)
        self.update()

    def paintEvent(self, event) -> None:
        if self._color.alpha() <= 0:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)


@dataclass
class _BackgroundOrb:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: QColor

    def render_radius(self) -> float:
        return self.radius * 1.65


class GlassRoot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._animate_orbs = False
        self._orb_rng = random.Random()
        self._orbs: list[_BackgroundOrb] = []
        self._orb_last_tick_s = time.monotonic()
        self._orb_timer: QTimer | None = None
        if self._animate_orbs:
            timer = QTimer(self)
            timer.setInterval(33)
            timer.timeout.connect(self._tick_orbs)
            timer.start()
            self._orb_timer = timer

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._constrain_orbs()

    def _theme_colors(self) -> list[QColor]:
        return [
            QColor(56, 189, 248),
            QColor(16, 185, 129),
            QColor(139, 92, 246),
            QColor(244, 63, 94),
            QColor(245, 158, 11),
        ]

    def _ensure_orbs(self) -> None:
        if self._orbs:
            return
        w, h = self.width(), self.height()
        if w < 80 or h < 80:
            return

        colors = self._theme_colors()
        orbs: list[_BackgroundOrb] = []
        for idx in range(9):
            radius = self._orb_rng.uniform(140.0, 260.0)
            render_r = radius * 1.65
            x = self._orb_rng.uniform(render_r, max(render_r, w - render_r))
            y = self._orb_rng.uniform(render_r, max(render_r, h - render_r))

            if self._animate_orbs:
                angle = self._orb_rng.uniform(0.0, 6.283185307179586)
                speed = self._orb_rng.uniform(8.0, 22.0)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
            else:
                vx = vy = 0.0

            orbs.append(_BackgroundOrb(
                x=x, y=y, vx=vx, vy=vy, radius=radius, color=colors[idx % len(colors)]
            ))

        self._orbs = orbs
        self._constrain_orbs()

    def _constrain_orbs(self) -> None:
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0 or not self._orbs:
            return
        for orb in self._orbs:
            r = orb.render_radius()
            orb.x = min(max(orb.x, r), w - r)
            orb.y = min(max(orb.y, r), h - r)

    def _tick_orbs(self) -> None:
        if not self._animate_orbs:
            return
        now_s = time.monotonic()
        dt = now_s - self._orb_last_tick_s
        self._orb_last_tick_s = now_s

        if dt <= 0:
            return
        dt = min(dt, 0.060)

        self._ensure_orbs()
        if not self._orbs:
            return

        w = float(max(1, self.width()))
        h = float(max(1, self.height()))
        for orb in self._orbs:
            orb.x += orb.vx * dt
            orb.y += orb.vy * dt

            r = orb.render_radius()
            if orb.x - r <= 0.0:
                orb.x = r
                orb.vx = abs(orb.vx)
            elif orb.x + r >= w:
                orb.x = w - r
                orb.vx = -abs(orb.vx)

            if orb.y - r <= 0.0:
                orb.y = r
                orb.vy = abs(orb.vy)
            elif orb.y + r >= h:
                orb.y = h - r
                orb.vy = -abs(orb.vy)

        self.update()

    def _paint_orbs(self, painter: QPainter) -> None:
        if not self._orbs:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        for orb in self._orbs:
            for shrink, alpha in ((1.0, 34), (0.82, 24), (0.66, 16)):
                r = max(1.0, orb.render_radius() * shrink)
                center = QPointF(float(orb.x), float(orb.y))
                grad = QRadialGradient(center, float(r))
                c = orb.color
                grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
                grad.setColorAt(0.55, QColor(c.red(), c.green(), c.blue(), int(alpha * 0.30)))
                grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
                painter.setBrush(grad)
                painter.drawEllipse(center, float(r), float(r))

        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.fillRect(self.rect(), QColor(10, 12, 18))

        self._ensure_orbs()
        self._paint_orbs(painter)

        w = max(1, self.width())
        h = max(1, self.height())
        shards = [
            (QColor(56, 189, 248, 38), [(0.00, 0.10), (0.38, 0.00), (0.55, 0.23), (0.22, 0.34)]),
            (QColor(16, 185, 129, 34), [(0.62, 0.00), (1.00, 0.14), (0.88, 0.42), (0.58, 0.28)]),
            (QColor(139, 92, 246, 28), [(0.08, 0.48), (0.28, 0.38), (0.52, 0.64), (0.20, 0.80)]),
            (QColor(244, 63, 94, 22), [(0.62, 0.56), (0.94, 0.46), (1.00, 0.82), (0.76, 1.00)]),
            (QColor(245, 158, 11, 18), [(0.00, 0.78), (0.20, 0.64), (0.40, 1.00), (0.00, 1.00)]),
        ]

        for color, points in shards:
            path = QPainterPath()
            x0, y0 = points[0]
            path.moveTo(int(x0 * w), int(y0 * h))
            for x, y in points[1:]:
                path.lineTo(int(x * w), int(y * h))
            path.closeSubpath()
            painter.fillPath(path, color)
            painter.setPen(QColor(255, 255, 255, 10))
            painter.drawPath(path)
