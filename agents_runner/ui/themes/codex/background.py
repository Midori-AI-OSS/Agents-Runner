"""Codex theme background rendering module.

Implements the two-band gradient with diagonal boundary and animated color blobs.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QWidget

# Codex theme constant: diagonal boundary angle in degrees
_CODEX_BOUNDARY_ANGLE_DEG: float = 15.0


def blend_colors(
    color1: QColor | str, color2: QColor | str, t: float
) -> QColor:
    """
    Blend between two colors using linear RGB interpolation.

    Args:
        color1: First color (QColor or hex string)
        color2: Second color (QColor or hex string)
        t: Blend factor from 0.0 (color1) to 1.0 (color2)

    Returns:
        Blended QColor
    """
    # Convert to QColor if needed
    c1 = QColor(color1) if isinstance(color1, str) else color1
    c2 = QColor(color2) if isinstance(color2, str) else color2

    # Clamp t to [0.0, 1.0]
    t = max(0.0, min(1.0, t))

    # Linear RGB interpolation
    r = int(c1.red() + (c2.red() - c1.red()) * t)
    g = int(c1.green() + (c2.green() - c1.green()) * t)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * t)

    return QColor(r, g, b)


def get_top_band_color(phase: float, cached_color: QColor | None, cached_phase: float) -> tuple[QColor, float]:
    """
    Get top band color by blending blue and green based on phase.

    Args:
        phase: Blend phase from 0.0 (Blue #60A5FA) to 1.0 (Green #34D399)
        cached_color: Previously cached color (or None)
        cached_phase: Previously cached phase value

    Returns:
        Tuple of (blended QColor for top band, phase used)
    """
    # Cache: skip recalculation if phase change < 0.01
    if cached_color is not None and abs(phase - cached_phase) < 0.01:
        return cached_color, cached_phase
    
    color = blend_colors("#60A5FA", "#34D399", phase)
    return color, phase


def get_bottom_band_color(phase: float, cached_color: QColor | None, cached_phase: float) -> tuple[QColor, float]:
    """
    Get bottom band color by blending between violet and orange based on phase.

    Args:
        phase: Blend phase from 0.0 (#A78BFA) to 1.0 (#FDBA74)
        cached_color: Previously cached color (or None)
        cached_phase: Previously cached phase value

    Returns:
        Tuple of (blended QColor for bottom band, phase used)
    """
    # Cache: skip recalculation if phase change < 0.01
    if cached_color is not None and abs(phase - cached_phase) < 0.01:
        return cached_color, cached_phase
    
    color = blend_colors("#A78BFA", "#FDBA74", phase)
    return color, phase


def calc_split_ratio() -> float:
    """
    Calculate split ratio oscillating between 0.3 and 0.6 with 180-second period.
    Uses sine wave for smooth oscillation with subtle jitter.
    """
    t = time.time()
    # Base oscillation: center at 0.45, amplitude of 0.15
    base = 0.45 + 0.15 * math.sin(t / 180.0 * 2.0 * math.pi)
    # Add subtle jitter (< 2% of range, which is 0.3 range → max 0.006)
    jitter = math.sin(t * 0.025) * 0.005
    return base + jitter


def calc_top_phase() -> float:
    """
    Calculate color blend phase for top band (0.0 to 1.0) with 140-second period.
    Uses cosine wave mapped to [0, 1] range with subtle jitter.
    """
    t = time.time()
    # Map cosine [-1, 1] to [0, 1]
    base = (1.0 + math.cos(t / 140.0 * 2.0 * math.pi)) * 0.5
    # Add subtle jitter (< 2% of range → max 0.02)
    jitter = math.sin(t * 0.0325) * 0.01
    return max(0.0, min(1.0, base + jitter))


def calc_bottom_phase() -> float:
    """
    Calculate color blend phase for bottom band (0.0 to 1.0) with 160-second period.
    Uses sine wave mapped to [0, 1] range with subtle jitter.
    """
    t = time.time()
    # Map sine [-1, 1] to [0, 1]
    base = (1.0 + math.sin(t / 160.0 * 2.0 * math.pi)) * 0.5
    # Add subtle jitter (< 2% of range → max 0.02)
    jitter = math.cos(t * 0.0275) * 0.008
    return max(0.0, min(1.0, base + jitter))


def paint_codex_background(
    painter: QPainter,
    rect: QWidget,
    split_ratio: float,
    top_phase: float,
    bottom_phase: float,
    cached_top_color: QColor | None,
    cached_top_phase: float,
    cached_bottom_color: QColor | None,
    cached_bottom_phase: float,
) -> tuple[QColor, float, QColor, float]:
    """
    Paint the two-band background composition for Codex theme.

    Renders animated background with:
    - Top band: DarkBlue to DarkGreen gradient
    - Bottom band: Dark accent gradient
    - Soft feathered diagonal boundary between bands
    - Large soft color blobs overlay

    Args:
        painter: QPainter instance to draw with
        rect: Rectangle defining the paint area
        split_ratio: Position of diagonal boundary (0.0-1.0)
        top_phase: Color blend phase for top band
        bottom_phase: Color blend phase for bottom band
        cached_top_color: Previously cached top color
        cached_top_phase: Previously cached top phase
        cached_bottom_color: Previously cached bottom color
        cached_bottom_phase: Previously cached bottom phase

    Returns:
        Tuple of (top_color, top_phase, bottom_color, bottom_phase) for caching
    """
    # Calculate colors based on phase (with caching)
    top_color, new_top_phase = get_top_band_color(top_phase, cached_top_color, cached_top_phase)
    bottom_color, new_bottom_phase = get_bottom_band_color(bottom_phase, cached_bottom_color, cached_bottom_phase)

    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0:
        return top_color, new_top_phase, bottom_color, new_bottom_phase

    theta = math.radians(float(_CODEX_BOUNDARY_ANGLE_DEG))
    m = math.tan(theta)
    n_len = math.hypot(m, 1.0)
    n_x = -m / n_len
    n_y = 1.0 / n_len

    mid_x = float(w) * 0.5
    mid_y = float(h) * float(split_ratio)

    extent = float(max(w, h)) * 1.15
    start = QPointF(mid_x - n_x * extent, mid_y - n_y * extent)
    end = QPointF(mid_x + n_x * extent, mid_y + n_y * extent)

    base_grad = QLinearGradient(start, end)
    base_grad.setColorAt(0.0, top_color.lighter(125))
    base_grad.setColorAt(0.42, blend_colors(top_color, bottom_color, 0.35))
    base_grad.setColorAt(0.62, blend_colors(top_color, bottom_color, 0.65))
    base_grad.setColorAt(1.0, bottom_color.lighter(120))
    painter.fillRect(0, 0, w, h, base_grad)

    # Overlay large, soft blobs for a more organic background.
    paint_codex_blobs(painter, rect)

    return top_color, new_top_phase, bottom_color, new_bottom_phase


def paint_band_boundary_diagonal(
    painter: QPainter,
    rect: QWidget,
    *,
    y_left: float,
    y_right: float,
    top_color: QColor,
    bottom_color: QColor,
) -> None:
    """
    Paint a diagonal gradient boundary between top and bottom bands.

    Args:
        painter: QPainter instance to draw with
        rect: Rectangle defining the paint area
        y_left: Y-coordinate of boundary at left edge
        y_right: Y-coordinate of boundary at right edge
        top_color: Color of the top band
        bottom_color: Color of the bottom band
    """
    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0:
        return

    gradient_extent = 420

    theta = math.radians(float(_CODEX_BOUNDARY_ANGLE_DEG))
    m = math.tan(theta)
    n_len = math.hypot(m, 1.0)
    n_x = -m / n_len
    n_y = 1.0 / n_len

    mid_x = float(w) * 0.5
    mid_y = (float(y_left) + float(y_right)) * 0.5
    start = QPointF(mid_x - n_x * gradient_extent, mid_y - n_y * gradient_extent)
    end = QPointF(mid_x + n_x * gradient_extent, mid_y + n_y * gradient_extent)
    gradient = QLinearGradient(start, end)

    gradient.setColorAt(0.0, top_color)
    gradient.setColorAt(0.15, blend_colors(top_color, bottom_color, 0.1))
    gradient.setColorAt(0.35, blend_colors(top_color, bottom_color, 0.3))
    gradient.setColorAt(0.5, blend_colors(top_color, bottom_color, 0.5))
    gradient.setColorAt(0.65, blend_colors(top_color, bottom_color, 0.7))
    gradient.setColorAt(0.85, blend_colors(top_color, bottom_color, 0.9))
    gradient.setColorAt(1.0, bottom_color)

    x0 = 0.0
    x1 = float(w)

    p0a = QPointF(x0 - n_x * gradient_extent, float(y_left) - n_y * gradient_extent)
    p1a = QPointF(x1 - n_x * gradient_extent, float(y_right) - n_y * gradient_extent)
    p1b = QPointF(x1 + n_x * gradient_extent, float(y_right) + n_y * gradient_extent)
    p0b = QPointF(x0 + n_x * gradient_extent, float(y_left) + n_y * gradient_extent)

    strip = QPainterPath()
    strip.moveTo(p0a)
    strip.lineTo(p1a)
    strip.lineTo(p1b)
    strip.lineTo(p0b)
    strip.closeSubpath()

    painter.save()
    painter.setClipPath(strip)
    painter.fillRect(0, 0, w, h, gradient)
    painter.restore()


def paint_codex_blobs(painter: QPainter, rect: QWidget) -> None:
    """
    Paint large, soft color blobs for organic background appearance.

    Args:
        painter: QPainter instance to draw with
        rect: Rectangle defining the paint area
    """
    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0:
        return

    # Keep motion subtle; tie to 4× slower global pacing.
    t = time.time() / 4.0
    size = float(min(w, h))

    blobs: tuple[tuple[float, float, float, float, QColor], ...] = (
        (
            0.18 + 0.03 * math.sin(t * 0.30),
            0.30 + 0.03 * math.cos(t * 0.24),
            0.75,
            0.55,
            QColor(147, 197, 253, 220),  # blue
        ),
        (
            0.58 + 0.03 * math.cos(t * 0.22 + 1.2),
            0.25 + 0.03 * math.sin(t * 0.18 + 0.7),
            0.85,
            0.60,
            QColor(196, 181, 253, 210),  # violet
        ),
        (
            0.78 + 0.02 * math.sin(t * 0.20 + 2.1),
            0.65 + 0.03 * math.cos(t * 0.16 + 1.8),
            0.95,
            0.65,
            QColor(253, 186, 116, 190),  # amber/orange
        ),
        (
            0.40 + 0.03 * math.sin(t * 0.17 + 3.0),
            0.78 + 0.03 * math.cos(t * 0.21 + 2.2),
            0.90,
            0.60,
            QColor(251, 113, 133, 175),  # pink
        ),
        (
            0.10 + 0.02 * math.cos(t * 0.19 + 4.0),
            0.78 + 0.02 * math.sin(t * 0.15 + 2.6),
            0.70,
            0.55,
            QColor(110, 231, 183, 170),  # emerald
        ),
    )

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)

    for nx, ny, rx_s, ry_s, c in blobs:
        center = QPointF(float(w) * float(nx), float(h) * float(ny))
        rx = max(1.0, size * float(rx_s))
        ry = max(1.0, size * float(ry_s))

        painter.save()
        painter.translate(center)
        painter.scale(float(rx), float(ry))

        grad = QRadialGradient(QPointF(0.0, 0.0), 1.0)
        grad.setColorAt(0.0, c)
        grad.setColorAt(
            0.45, QColor(c.red(), c.green(), c.blue(), int(c.alpha() * 0.28))
        )
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))

        painter.setBrush(grad)
        painter.drawEllipse(QPointF(0.0, 0.0), 1.0, 1.0)
        painter.restore()

    painter.restore()


def paint_band_boundary(
    painter: QPainter,
    rect: QWidget,
    split_ratio: float,
    top_color: QColor,
    bottom_color: QColor,
    cached_gradient: QLinearGradient | None,
    cached_boundary_y: int,
    cached_gradient_top_color: QColor | None,
    cached_gradient_bottom_color: QColor | None,
) -> tuple[QLinearGradient, int, QColor, QColor]:
    """
    Paint a soft, feathered gradient boundary between top and bottom bands.

    Args:
        painter: QPainter instance to draw with
        rect: Rectangle defining the paint area
        split_ratio: Position of boundary (0.0-1.0, where 0.3 = 30% from top)
        top_color: Color of the top band
        bottom_color: Color of the bottom band
        cached_gradient: Previously cached gradient (or None)
        cached_boundary_y: Previously cached boundary Y position
        cached_gradient_top_color: Previously cached top color
        cached_gradient_bottom_color: Previously cached bottom color

    Returns:
        Tuple of (gradient, boundary_y, top_color_copy, bottom_color_copy) for caching
    """
    # Calculate boundary line position
    boundary_y = int(rect.height() * split_ratio)

    # Check if we need to rebuild gradient
    colors_changed = (
        cached_gradient_top_color is None
        or cached_gradient_bottom_color is None
        or top_color != cached_gradient_top_color
        or bottom_color != cached_gradient_bottom_color
    )
    boundary_changed = boundary_y != cached_boundary_y

    # Rebuild gradient only if colors or boundary changed
    if cached_gradient is None or colors_changed or boundary_changed:
        # Define gradient region (80px above and below boundary)
        gradient_extent = 80
        gradient_start_y = boundary_y - gradient_extent
        gradient_end_y = boundary_y + gradient_extent

        # Create linear gradient perpendicular to boundary
        gradient = QLinearGradient(0, gradient_start_y, 0, gradient_end_y)

        # Add 7 color stops for smooth feathering
        # Positions: 0.0, 0.15, 0.35, 0.5, 0.65, 0.85, 1.0
        gradient.setColorAt(0.0, top_color)
        gradient.setColorAt(0.15, blend_colors(top_color, bottom_color, 0.1))
        gradient.setColorAt(0.35, blend_colors(top_color, bottom_color, 0.3))
        gradient.setColorAt(0.5, blend_colors(top_color, bottom_color, 0.5))
        gradient.setColorAt(0.65, blend_colors(top_color, bottom_color, 0.7))
        gradient.setColorAt(0.85, blend_colors(top_color, bottom_color, 0.9))
        gradient.setColorAt(1.0, bottom_color)

        cached_gradient = gradient
        cached_boundary_y = boundary_y
        cached_gradient_top_color = QColor(top_color)
        cached_gradient_bottom_color = QColor(bottom_color)
    else:
        gradient = cached_gradient

    # Define gradient region for fillRect
    gradient_extent = 80
    gradient_start_y = boundary_y - gradient_extent

    # Apply gradient to the boundary region
    painter.fillRect(
        0, gradient_start_y, rect.width(), gradient_extent * 2, gradient
    )

    return gradient, boundary_y, cached_gradient_top_color, cached_gradient_bottom_color
