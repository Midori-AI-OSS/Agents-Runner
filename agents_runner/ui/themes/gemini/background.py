from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt


@dataclass
class _GeminiChromaOrb:
    side: str
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color_idx: int
    color_to_idx: int
    color_elapsed_s: float
    color_blend_s: float


def gemini_palette() -> tuple[QColor, ...]:
    return (
        QColor("#4285F4"),  # blue
        QColor("#EA4335"),  # red
        QColor("#FBBC04"),  # yellow
        QColor("#34A853"),  # green
    )


def ensure_gemini_orbs(
    orbs: list[_GeminiChromaOrb],
    rng: random.Random,
    width: int,
    height: int,
) -> list[_GeminiChromaOrb]:
    if orbs:
        return orbs
    w, h = width, height
    if w < 80 or h < 80:
        return orbs

    new_orbs: list[_GeminiChromaOrb] = []
    # Fixed Google colors: one orb per color, no color cycling.
    # Place each orb near a different quadrant initially for balance.
    color_init: tuple[tuple[str, int, float, float], ...] = (
        ("blue", 0, 0.18, 0.34),
        ("red", 1, 0.84, 0.24),
        ("yellow", 2, 0.22, 0.86),
        ("green", 3, 0.88, 0.70),
    )
    for name, color_idx, fx, fy in color_init:
        radius = float(rng.uniform(210.0, 320.0))
        render_r = radius * 1.55
        x = float(w) * fx + rng.uniform(-45.0, 45.0)
        y = float(h) * fy + rng.uniform(-45.0, 45.0)
        x = min(max(x, render_r), max(render_r, float(w) - render_r))
        y = min(max(y, render_r), max(render_r, float(h) - render_r))

        angle = rng.uniform(0.0, 6.283185307179586)
        speed = rng.uniform(4.5, 10.5)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed

        new_orbs.append(
            _GeminiChromaOrb(
                side=name,
                x=float(x),
                y=float(y),
                vx=float(vx),
                vy=float(vy),
                radius=float(radius),
                color_idx=int(color_idx),
                color_to_idx=int(color_idx),
                color_elapsed_s=0.0,
                color_blend_s=1.0,
            )
        )

    # Small relaxation step to keep the four colors from clustering.
    desired = float(min(w, h)) * 0.40
    for _ in range(18):
        moved = False
        for i in range(len(new_orbs)):
            for j in range(i + 1, len(new_orbs)):
                a = new_orbs[i]
                b = new_orbs[j]
                dx = float(b.x - a.x)
                dy = float(b.y - a.y)
                d = math.hypot(dx, dy)
                if d <= 1e-6 or d >= desired:
                    continue
                push = (desired - d) * 0.5
                ux = dx / d
                uy = dy / d
                a.x -= ux * push
                a.y -= uy * push
                b.x += ux * push
                b.y += uy * push
                moved = True
        if not moved:
            break

    constrain_gemini_orbs(new_orbs, width, height)
    return new_orbs


def constrain_gemini_orbs(
    orbs: list[_GeminiChromaOrb],
    width: int,
    height: int,
) -> None:
    if not orbs:
        return
    w = float(max(1, width))
    h = float(max(1, height))
    for orb in orbs:
        r = orb.radius * 1.55
        orb.x = min(max(orb.x, r), max(r, w - r))
        orb.y = min(max(orb.y, r), max(r, h - r))


def tick_gemini_chroma_orbs(
    orbs: list[_GeminiChromaOrb],
    rng: random.Random,
    width: int,
    height: int,
    dt_s: float,
) -> None:
    if not orbs:
        return

    w = float(max(1, width))
    h = float(max(1, height))

    for orb in orbs:
        orb.x += orb.vx * dt_s
        orb.y += orb.vy * dt_s

        r = orb.radius * 1.55
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

        # Gentle drift so paths aren't perfectly periodic.
        if rng.random() < (0.05 * dt_s):
            orb.vx *= float(rng.uniform(0.985, 1.015))
            orb.vy *= float(rng.uniform(0.985, 1.015))

    constrain_gemini_orbs(orbs, width, height)


def paint_gemini_background(
    painter: QPainter,
    rect: QWidget,
    orbs: list[_GeminiChromaOrb],
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)

    w = max(1, rect.width())
    h = max(1, rect.height())

    base = QLinearGradient(0, 0, 0, h)
    base.setColorAt(0.0, QColor("#222C3F"))
    base.setColorAt(0.55, QColor("#172133"))
    base.setColorAt(1.0, QColor("#10192A"))
    painter.fillRect(rect, base)

    if orbs:
        palette = gemini_palette()
        painter.setPen(Qt.NoPen)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for orb in orbs:
            c = palette[int(orb.color_idx) % len(palette)]
            center = QPointF(float(orb.x), float(orb.y))
            rx = max(1.0, float(orb.radius) * 1.70)
            ry = max(1.0, float(orb.radius) * 1.45)

            painter.save()
            painter.translate(center)
            painter.scale(float(rx), float(ry))

            # Codex-style soft blob, but locked to Google colors.
            grad = QRadialGradient(QPointF(0.0, 0.0), 1.0)
            grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 220))
            grad.setColorAt(
                0.45, QColor(c.red(), c.green(), c.blue(), int(220 * 0.28))
            )
            grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
            painter.setBrush(grad)
            painter.drawEllipse(QPointF(0.0, 0.0), 1.0, 1.0)
            painter.restore()

    vignette = QRadialGradient(QPointF(w * 0.5, h * 0.45), float(max(w, h) * 0.85))
    vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
    vignette.setColorAt(1.0, QColor(0, 0, 0, 46))
    painter.fillRect(rect, vignette)

    painter.restore()
