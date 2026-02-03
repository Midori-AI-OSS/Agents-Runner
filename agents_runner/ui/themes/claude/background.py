from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient


_CLAUDE_SEGMENT_LIFETIME_S: float = 90.0
_CLAUDE_SEGMENT_FADE_IN_S: float = 1.8


@dataclass
class _ClaudeBranchTip:
    x: float
    y: float
    angle: float
    thickness: float
    depth: int
    speed: float


@dataclass
class _ClaudeBranchSegment:
    x0: float
    y0: float
    x1: float
    y1: float
    thickness: float
    age_s: float
    tone: int


def claude_palette(
    palette_phase: float, blend_colors_fn
) -> tuple[QColor, QColor, QColor, QColor]:
    """
    Warm dark palette blended between "browser dark" and "code" moods.
    Returns: (top, bottom, accent, accent_dim)
    """
    t = float(palette_phase)
    top = blend_colors_fn("#201D18", "#1B1612", t)
    bottom = blend_colors_fn("#1A1815", "#141210", t)
    accent = blend_colors_fn("#C15F3C", "#A14A2F", 0.35 + 0.25 * (1.0 - t))
    accent_dim = blend_colors_fn("#C15F3C", "#A14A2F", 0.75)
    return top, bottom, accent, accent_dim


def ensure_claude_tree(
    claude_tips: list[_ClaudeBranchTip],
    claude_rng: random.Random,
    width: int,
    height: int,
    now_s: float,
) -> tuple[list[_ClaudeBranchTip], float]:
    """
    Ensure the Claude tree is initialized. Returns (tips, next_reset_s).
    """
    if claude_tips:
        # Return a placeholder next_reset_s - will be managed by reset function
        return claude_tips, now_s + 60.0

    w, h = width, height
    if w < 80 or h < 80:
        return claude_tips, now_s + 60.0

    return reset_claude_tree(claude_rng, width, height, now_s=now_s)


def reset_claude_tree(
    claude_rng: random.Random,
    width: int,
    height: int,
    *,
    now_s: float,
) -> tuple[list[_ClaudeBranchTip], float]:
    """
    Reset the Claude tree to initial state with new root branches.
    Returns (tips, next_reset_s).
    """
    claude_tips: list[_ClaudeBranchTip] = []

    w = float(max(1, width))
    h = float(max(1, height))
    if w < 80.0 or h < 80.0:
        return claude_tips, now_s + 60.0

    root_count = int(claude_rng.randint(1, 2))
    for _ in range(root_count):
        side = claude_rng.choice(("left", "right", "bottom", "top"))
        if side == "left":
            x = 0.0
            y = claude_rng.uniform(h * 0.12, h * 0.88)
            angle = claude_rng.uniform(-0.35, 0.35)
        elif side == "right":
            x = w
            y = claude_rng.uniform(h * 0.12, h * 0.88)
            angle = math.pi + claude_rng.uniform(-0.35, 0.35)
        elif side == "top":
            x = claude_rng.uniform(w * 0.18, w * 0.82)
            y = 0.0
            angle = (math.pi * 0.5) + claude_rng.uniform(-0.45, 0.45)
        else:
            x = claude_rng.uniform(w * 0.18, w * 0.82)
            y = h
            angle = -(math.pi * 0.5) + claude_rng.uniform(-0.45, 0.45)

        claude_tips.append(
            _ClaudeBranchTip(
                x=float(x),
                y=float(y),
                angle=float(angle),
                thickness=float(claude_rng.uniform(1.0, 1.8)),
                depth=0,
                speed=float(claude_rng.uniform(16.0, 24.0)),
            )
        )

    next_reset_s = float(now_s) + float(claude_rng.uniform(55.0, 85.0))
    return claude_tips, next_reset_s


def tick_claude_tree(
    claude_tips: list[_ClaudeBranchTip],
    claude_segments: list[_ClaudeBranchSegment],
    claude_rng: random.Random,
    width: int,
    height: int,
    next_reset_s: float,
    *,
    dt_s: float,
    now_s: float,
) -> tuple[list[_ClaudeBranchTip], list[_ClaudeBranchSegment], float, float]:
    """
    Advance the Claude tree animation by one timestep.
    Returns (tips, segments, palette_phase, next_reset_s).
    """
    palette_phase = (1.0 + math.sin(time.time() / 240.0 * 2.0 * math.pi)) * 0.5

    w = float(max(1, width))
    h = float(max(1, height))
    if w < 80.0 or h < 80.0:
        return claude_tips, claude_segments, palette_phase, next_reset_s

    if not claude_tips or now_s >= next_reset_s:
        claude_tips, next_reset_s = reset_claude_tree(
            claude_rng, width, height, now_s=now_s
        )

    for seg in claude_segments:
        seg.age_s += float(dt_s)

    max_age_s = float(_CLAUDE_SEGMENT_LIFETIME_S)
    claude_segments = [s for s in claude_segments if s.age_s <= max_age_s]

    tips_next: list[_ClaudeBranchTip] = []
    max_tips = 14
    max_depth = 180

    for tip in claude_tips:
        if tip.depth > max_depth or tip.thickness < 0.55:
            continue

        if claude_rng.random() < (0.020 * dt_s) and tip.depth >= 10:
            continue

        step = tip.speed * dt_s
        if step <= 0.1:
            tips_next.append(tip)
            continue

        # Apply a small dt-scaled drift to avoid visible "jumps" in direction.
        drift = claude_rng.uniform(-0.28, 0.28) * dt_s
        angle = tip.angle + drift
        nx = tip.x + math.cos(angle) * step
        ny = tip.y + math.sin(angle) * step

        # Keep growth loosely contained inside the viewport with a small buffer.
        if nx < -40.0 or nx > w + 40.0 or ny < -40.0 or ny > h + 40.0:
            continue

        roll = claude_rng.random()
        tone = 0 if roll < 0.68 else (1 if roll < 0.90 else 2)
        claude_segments.append(
            _ClaudeBranchSegment(
                x0=float(tip.x),
                y0=float(tip.y),
                x1=float(nx),
                y1=float(ny),
                thickness=float(tip.thickness),
                age_s=0.0,
                tone=int(tone),
            )
        )

        next_tip = _ClaudeBranchTip(
            x=float(nx),
            y=float(ny),
            angle=float(angle),
            thickness=float(tip.thickness * claude_rng.uniform(0.985, 0.997)),
            depth=int(tip.depth + 1),
            speed=float(tip.speed * claude_rng.uniform(0.985, 1.01)),
        )

        if len(tips_next) < max_tips:
            tips_next.append(next_tip)

        if len(tips_next) < max_tips and tip.depth >= 2:
            branch_chance = 0.065 * dt_s
            if claude_rng.random() < branch_chance:
                spread = claude_rng.uniform(0.28, 0.72)
                sign = -1.0 if claude_rng.random() < 0.5 else 1.0
                tips_next.append(
                    _ClaudeBranchTip(
                        x=float(nx),
                        y=float(ny),
                        angle=float(angle + sign * spread),
                        thickness=float(tip.thickness * claude_rng.uniform(0.78, 0.92)),
                        depth=int(tip.depth + 1),
                        speed=float(tip.speed * claude_rng.uniform(0.90, 1.05)),
                    )
                )

    claude_tips = tips_next
    if len(claude_segments) > 900:
        claude_segments = claude_segments[-900:]

    return claude_tips, claude_segments, palette_phase, next_reset_s


def paint_claude_background(
    painter: QPainter,
    rect: QRect,
    claude_tips: list[_ClaudeBranchTip],
    claude_segments: list[_ClaudeBranchSegment],
    claude_rng: random.Random,
    palette_phase: float,
    width: int,
    height: int,
    now_s: float,
    blend_colors_fn,
) -> tuple[list[_ClaudeBranchTip], float]:
    """
    Paint the Claude background with animated branching tree pattern.
    Returns (tips, next_reset_s) after ensuring tree is initialized.
    """
    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0:
        return claude_tips, now_s + 60.0

    claude_tips, next_reset_s = ensure_claude_tree(
        claude_tips, claude_rng, width, height, now_s
    )
    top, bottom, accent, accent_dim = claude_palette(palette_phase, blend_colors_fn)

    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0.0, top)
    grad.setColorAt(0.55, blend_colors_fn(top, bottom, 0.55))
    grad.setColorAt(1.0, bottom)
    painter.fillRect(0, 0, w, h, grad)

    vignette = QRadialGradient(QPointF(w * 0.5, h * 0.5), float(max(w, h)) * 0.75)
    vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
    vignette.setColorAt(1.0, QColor(0, 0, 0, 44))
    painter.fillRect(0, 0, w, h, vignette)

    if not claude_segments:
        return claude_tips, next_reset_s

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)

    max_age_s = float(_CLAUDE_SEGMENT_LIFETIME_S)
    for seg in claude_segments:
        t = max(0.0, min(1.0, float(seg.age_s) / max_age_s))
        fade_out = 1.0 - t
        fade_in = min(1.0, float(seg.age_s) / float(_CLAUDE_SEGMENT_FADE_IN_S))
        fade = fade_in * fade_out

        if seg.tone == 0:
            base_color = accent
        elif seg.tone == 2:
            base_color = accent_dim
        else:
            base_color = QColor(232, 230, 227)

        core_alpha = int(92 * fade)
        glow_alpha = int(34 * fade)
        haze_alpha = int(18 * fade)

        for width_scale, alpha in (
            (3.8, haze_alpha),
            (2.2, glow_alpha),
            (1.0, core_alpha),
        ):
            if alpha <= 0:
                continue
            pen = QPen(
                QColor(base_color.red(), base_color.green(), base_color.blue(), alpha),
                max(1.0, float(seg.thickness) * width_scale),
                Qt.SolidLine,
                Qt.PenCapStyle.FlatCap,
                Qt.PenJoinStyle.MiterJoin,
            )
            painter.setPen(pen)
            painter.drawLine(
                QPointF(float(seg.x0), float(seg.y0)),
                QPointF(float(seg.x1), float(seg.y1)),
            )

    painter.restore()
    return claude_tips, next_reset_s
