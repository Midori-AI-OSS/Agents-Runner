from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    Property,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor
from PySide6.QtGui import QLinearGradient
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QRadialGradient
from PySide6.QtGui import QResizeEvent
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

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._color.alpha() <= 0:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)


@dataclass(frozen=True)
class _AgentTheme:
    name: str
    base: QColor
    orb_colors: tuple[QColor, ...]
    shard_colors: tuple[QColor, ...]
    shard_points: tuple[tuple[tuple[float, float], ...], ...]


_SHARD_POINTS_CODEX: tuple[tuple[tuple[float, float], ...], ...] = (
    ((0.00, 0.10), (0.38, 0.00), (0.55, 0.23), (0.22, 0.34)),
    ((0.62, 0.00), (1.00, 0.14), (0.88, 0.42), (0.58, 0.28)),
    ((0.08, 0.48), (0.28, 0.38), (0.52, 0.64), (0.20, 0.80)),
    ((0.62, 0.56), (0.94, 0.46), (1.00, 0.82), (0.76, 1.00)),
    ((0.00, 0.78), (0.20, 0.64), (0.40, 1.00), (0.00, 1.00)),
)

_SHARD_POINTS_COPILOT: tuple[tuple[tuple[float, float], ...], ...] = (
    ((0.00, 0.04), (0.30, 0.00), (0.44, 0.18), (0.16, 0.28)),
    ((0.54, 0.00), (1.00, 0.06), (0.86, 0.34), (0.62, 0.20)),
    ((0.30, 0.38), (0.58, 0.30), (0.72, 0.56), (0.40, 0.66)),
    ((0.70, 0.64), (1.00, 0.56), (1.00, 1.00), (0.80, 1.00)),
    ((0.00, 0.70), (0.22, 0.56), (0.46, 0.86), (0.14, 1.00), (0.00, 1.00)),
)

_SHARD_POINTS_CLAUDE: tuple[tuple[tuple[float, float], ...], ...] = (
    ((0.00, 0.08), (0.18, 0.00), (0.30, 0.12), (0.10, 0.24)),
    ((0.30, 0.00), (0.52, 0.00), (0.44, 0.34), (0.24, 0.26)),
    ((0.54, 0.18), (0.74, 0.08), (0.82, 0.40), (0.56, 0.48)),
    ((0.72, 0.56), (0.92, 0.48), (1.00, 0.78), (0.84, 0.90)),
    ((0.00, 0.64), (0.22, 0.48), (0.38, 0.72), (0.18, 1.00), (0.00, 1.00)),
)

_SHARD_POINTS_GEMINI: tuple[tuple[tuple[float, float], ...], ...] = (
    ((0.00, 0.00), (0.34, 0.00), (0.14, 0.26)),
    ((0.66, 0.00), (1.00, 0.00), (0.88, 0.30), (0.70, 0.18)),
    ((0.10, 0.44), (0.34, 0.34), (0.24, 0.70), (0.00, 0.62)),
    ((0.62, 0.42), (0.92, 0.34), (1.00, 0.56), (0.74, 0.66)),
    ((0.32, 0.84), (0.62, 0.74), (0.84, 1.00), (0.18, 1.00)),
)


def _theme_for_agent(agent_cli: str) -> _AgentTheme:
    agent_cli = str(agent_cli or "codex").strip().lower()
    if agent_cli == "copilot":
        return _AgentTheme(
            name="copilot",
            base=QColor(13, 17, 23),  # #0D1117
            orb_colors=(
                QColor(192, 110, 255),  # #C06EFF
                QColor(95, 237, 131),  # #5FED83
                QColor(80, 29, 175),  # #501DAF
                QColor(88, 166, 255),
                QColor(139, 148, 158),
            ),
            shard_colors=(
                QColor(192, 110, 255, 34),
                QColor(95, 237, 131, 26),
                QColor(88, 166, 255, 20),
                QColor(80, 29, 175, 18),
                QColor(139, 148, 158, 14),
            ),
            shard_points=_SHARD_POINTS_COPILOT,
        )
    if agent_cli == "claude":
        return _AgentTheme(
            name="claude",
            base=QColor(245, 245, 240),  # #F5F5F0
            orb_colors=(
                QColor(174, 86, 48),  # #AE5630
                QColor(221, 217, 206),  # #DDD9CE
                QColor(107, 106, 104),  # #6B6A68
                QColor(196, 99, 58),  # #C4633A
                QColor(26, 26, 24),
            ),
            shard_colors=(
                QColor(174, 86, 48, 18),
                QColor(196, 99, 58, 14),
                QColor(221, 217, 206, 14),
                QColor(107, 106, 104, 10),
                QColor(26, 26, 24, 8),
            ),
            shard_points=_SHARD_POINTS_CLAUDE,
        )
    if agent_cli == "gemini":
        return _AgentTheme(
            name="gemini",
            base=QColor(18, 20, 28),  # #12141C (avoid white flash)
            orb_colors=(
                QColor(66, 133, 244),  # #4285F4
                QColor(234, 67, 53),  # #EA4335
                QColor(251, 188, 4),  # #FBBC04
                QColor(52, 168, 83),  # #34A853
                QColor(154, 160, 166),  # #9AA0A6
            ),
            shard_colors=(
                QColor(66, 133, 244, 16),
                QColor(234, 67, 53, 14),
                QColor(251, 188, 4, 12),
                QColor(52, 168, 83, 12),
                QColor(154, 160, 166, 10),
            ),
            shard_points=_SHARD_POINTS_GEMINI,
        )

    # codex / ChatGPT neutral
    return _AgentTheme(
        name="codex",
        base=QColor(12, 13, 15),
        orb_colors=(
            QColor(31, 117, 254),  # #1F75FE
            QColor(0, 165, 90),  # #00A55A
            QColor(178, 186, 194),
            QColor(92, 99, 112),
            QColor(240, 240, 240),
        ),
        shard_colors=(
            QColor(31, 117, 254, 20),
            QColor(0, 165, 90, 16),
            QColor(178, 186, 194, 10),
            QColor(92, 99, 112, 10),
            QColor(240, 240, 240, 8),
        ),
        shard_points=_SHARD_POINTS_CODEX,
    )


@dataclass
class _BackgroundOrb:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color_idx: int

    def render_radius(self) -> float:
        return self.radius * 1.65


class GlassRoot(QWidget):
    _CODEX_BOUNDARY_ANGLE_DEG: float = 15.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._animate_orbs = False
        self._orb_rng = random.Random()
        self._orbs: list[_BackgroundOrb] = []
        self._orb_last_tick_s = time.monotonic()
        self._orb_timer: QTimer | None = None

        self._theme = _theme_for_agent("codex")
        self._theme_to: _AgentTheme | None = None
        self._theme_blend = 0.0
        self._theme_anim: QPropertyAnimation | None = None

        # Codex background animation phase parameters
        self._codex_split_ratio: float = 0.45
        self._codex_color_blend_phase_top: float = 0.0
        self._codex_color_blend_phase_bottom: float = 0.0
        self._codex_jitter_x: float = 0.0
        self._codex_jitter_y: float = 0.0

        # Performance optimization: cache colors and gradient
        self._cached_top_color: QColor | None = None
        self._cached_bottom_color: QColor | None = None
        self._cached_top_phase: float = -1.0
        self._cached_bottom_phase: float = -1.0
        self._cached_gradient: QLinearGradient | None = None
        self._cached_boundary_y: int = -1
        self._cached_gradient_top_color: QColor | None = None
        self._cached_gradient_bottom_color: QColor | None = None

        if self._animate_orbs:
            timer = QTimer(self)
            timer.setInterval(33)
            timer.timeout.connect(self._tick_orbs)
            timer.start()
            self._orb_timer = timer

        # Start Codex background animation timer
        codex_timer = QTimer(self)
        codex_timer.setInterval(100)
        codex_timer.timeout.connect(self._update_background_animation)
        codex_timer.start()

    @staticmethod
    def _darken_overlay_alpha(theme: _AgentTheme) -> int:
        if theme.name == "codex":
            return 28
        lightness = float(theme.base.lightnessF())
        # Keep the background readable without crushing the palette into near-black.
        # Slightly stronger darkening on light themes, lighter on dark themes.
        alpha = int(165 + 55 * lightness)
        return int(min(max(alpha, 0), 255))

    def set_agent_theme(self, agent_cli: str) -> None:
        theme = _theme_for_agent(agent_cli)
        if theme.name == self._theme.name:
            return

        self._theme_to = theme
        self._set_theme_blend(0.0)

        if self._theme_anim is not None:
            self._theme_anim.stop()

        anim = QPropertyAnimation(self, b"themeBlend", self)
        anim.setDuration(7000)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def _finish() -> None:
            self._theme = theme
            self._theme_to = None
            self._set_theme_blend(0.0)

        anim.finished.connect(_finish)
        anim.start()
        self._theme_anim = anim

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._constrain_orbs()

    def _get_theme_blend(self) -> float:
        return float(self._theme_blend)

    def _set_theme_blend(self, value: float) -> None:
        self._theme_blend = float(min(max(value, 0.0), 1.0))
        self.update()

    themeBlend = Property(float, _get_theme_blend, _set_theme_blend)

    def _ensure_orbs(self) -> None:
        if self._orbs:
            return
        w, h = self.width(), self.height()
        if w < 80 or h < 80:
            return

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

            orbs.append(
                _BackgroundOrb(
                    x=x,
                    y=y,
                    vx=vx,
                    vy=vy,
                    radius=radius,
                    color_idx=idx,
                )
            )

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

    def _blend_colors(
        self, color1: QColor | str, color2: QColor | str, t: float
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

    def _get_top_band_color(self, phase: float) -> QColor:
        """
        Get top band color by blending blue and green based on phase.

        Args:
            phase: Blend phase from 0.0 (Blue #60A5FA) to 1.0 (Green #34D399)

        Returns:
            Blended QColor for top band
        """
        # Cache: skip recalculation if phase change < 0.01
        if self._cached_top_color is not None and abs(phase - self._cached_top_phase) < 0.01:
            return self._cached_top_color
        
        color = self._blend_colors("#60A5FA", "#34D399", phase)
        self._cached_top_color = color
        self._cached_top_phase = phase
        return color

    def _get_bottom_band_color(self, phase: float) -> QColor:
        """
        Get bottom band color by blending between violet and orange based on phase.

        Args:
            phase: Blend phase from 0.0 (#A78BFA) to 1.0 (#FDBA74)

        Returns:
            Blended QColor for bottom band
        """
        # Cache: skip recalculation if phase change < 0.01
        if self._cached_bottom_color is not None and abs(phase - self._cached_bottom_phase) < 0.01:
            return self._cached_bottom_color
        
        color = self._blend_colors("#A78BFA", "#FDBA74", phase)
        self._cached_bottom_color = color
        self._cached_bottom_phase = phase
        return color

    def _calc_split_ratio(self) -> float:
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

    def _calc_top_phase(self) -> float:
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

    def _calc_bottom_phase(self) -> float:
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

    def _update_background_animation(self) -> None:
        """Update Codex background animation phase parameters."""
        self._codex_split_ratio = self._calc_split_ratio()
        self._codex_color_blend_phase_top = self._calc_top_phase()
        self._codex_color_blend_phase_bottom = self._calc_bottom_phase()
        # Trigger repaint if using Codex theme
        if self._theme.name == "codex":
            self.update()

    def _paint_codex_background(self, painter: QPainter, rect: QWidget) -> None:
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
        """
        # Use cached phase values (updated by timer)
        split_ratio = self._codex_split_ratio
        top_phase = self._codex_color_blend_phase_top
        bottom_phase = self._codex_color_blend_phase_bottom

        # Calculate colors based on phase (with caching)
        top_color = self._get_top_band_color(top_phase)
        bottom_color = self._get_bottom_band_color(bottom_phase)

        w = int(rect.width())
        h = int(rect.height())
        if w <= 0 or h <= 0:
            return

        theta = math.radians(float(self._CODEX_BOUNDARY_ANGLE_DEG))
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
        base_grad.setColorAt(0.42, self._blend_colors(top_color, bottom_color, 0.35))
        base_grad.setColorAt(0.62, self._blend_colors(top_color, bottom_color, 0.65))
        base_grad.setColorAt(1.0, bottom_color.lighter(120))
        painter.fillRect(0, 0, w, h, base_grad)

        # Overlay large, soft blobs for a more organic background.
        self._paint_codex_blobs(painter, rect)

    def _paint_band_boundary_diagonal(
        self,
        painter: QPainter,
        rect: QWidget,
        *,
        y_left: float,
        y_right: float,
        top_color: QColor,
        bottom_color: QColor,
    ) -> None:
        w = int(rect.width())
        h = int(rect.height())
        if w <= 0 or h <= 0:
            return

        gradient_extent = 420

        theta = math.radians(float(self._CODEX_BOUNDARY_ANGLE_DEG))
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
        gradient.setColorAt(0.15, self._blend_colors(top_color, bottom_color, 0.1))
        gradient.setColorAt(0.35, self._blend_colors(top_color, bottom_color, 0.3))
        gradient.setColorAt(0.5, self._blend_colors(top_color, bottom_color, 0.5))
        gradient.setColorAt(0.65, self._blend_colors(top_color, bottom_color, 0.7))
        gradient.setColorAt(0.85, self._blend_colors(top_color, bottom_color, 0.9))
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

    def _paint_codex_blobs(self, painter: QPainter, rect: QWidget) -> None:
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

    def _paint_band_boundary(
        self,
        painter: QPainter,
        rect: QWidget,
        split_ratio: float,
        top_color: QColor,
        bottom_color: QColor,
    ) -> None:
        """
        Paint a soft, feathered gradient boundary between top and bottom bands.

        Args:
            painter: QPainter instance to draw with
            rect: Rectangle defining the paint area
            split_ratio: Position of boundary (0.0-1.0, where 0.3 = 30% from top)
            top_color: Color of the top band
            bottom_color: Color of the bottom band
        """
        # Calculate boundary line position
        boundary_y = int(rect.height() * split_ratio)

        # Check if we need to rebuild gradient
        colors_changed = (
            self._cached_gradient_top_color is None
            or self._cached_gradient_bottom_color is None
            or top_color != self._cached_gradient_top_color
            or bottom_color != self._cached_gradient_bottom_color
        )
        boundary_changed = boundary_y != self._cached_boundary_y

        # Rebuild gradient only if colors or boundary changed
        if self._cached_gradient is None or colors_changed or boundary_changed:
            # Define gradient region (80px above and below boundary)
            gradient_extent = 80
            gradient_start_y = boundary_y - gradient_extent
            gradient_end_y = boundary_y + gradient_extent

            # Create linear gradient perpendicular to boundary
            gradient = QLinearGradient(0, gradient_start_y, 0, gradient_end_y)

            # Add 7 color stops for smooth feathering
            # Positions: 0.0, 0.15, 0.35, 0.5, 0.65, 0.85, 1.0
            gradient.setColorAt(0.0, top_color)
            gradient.setColorAt(0.15, self._blend_colors(top_color, bottom_color, 0.1))
            gradient.setColorAt(0.35, self._blend_colors(top_color, bottom_color, 0.3))
            gradient.setColorAt(0.5, self._blend_colors(top_color, bottom_color, 0.5))
            gradient.setColorAt(0.65, self._blend_colors(top_color, bottom_color, 0.7))
            gradient.setColorAt(0.85, self._blend_colors(top_color, bottom_color, 0.9))
            gradient.setColorAt(1.0, bottom_color)

            self._cached_gradient = gradient
            self._cached_boundary_y = boundary_y
            self._cached_gradient_top_color = QColor(top_color)
            self._cached_gradient_bottom_color = QColor(bottom_color)

        # Define gradient region for fillRect
        gradient_extent = 80
        gradient_start_y = boundary_y - gradient_extent

        # Apply gradient to the boundary region
        painter.fillRect(
            0, gradient_start_y, rect.width(), gradient_extent * 2, self._cached_gradient
        )

    def _paint_orbs(self, painter: QPainter, theme: _AgentTheme) -> None:
        if not self._orbs:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        colors = theme.orb_colors
        if not colors:
            painter.restore()
            return

        for orb in self._orbs:
            c = colors[orb.color_idx % len(colors)]
            for shrink, alpha in ((1.0, 34), (0.82, 24), (0.66, 16)):
                r = max(1.0, orb.render_radius() * shrink)
                center = QPointF(float(orb.x), float(orb.y))
                grad = QRadialGradient(center, float(r))
                grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
                grad.setColorAt(
                    0.55, QColor(c.red(), c.green(), c.blue(), int(alpha * 0.30))
                )
                grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
                painter.setBrush(grad)
                painter.drawEllipse(center, float(r), float(r))

        painter.restore()

    def _paint_theme(self, painter: QPainter, theme: _AgentTheme) -> None:
        if theme.name == "codex":
            self._paint_codex_background(painter, self.rect())
            return  # Skip orbs and shards for Codex

        painter.fillRect(self.rect(), theme.base)

        self._ensure_orbs()
        self._paint_orbs(painter, theme)

        w = max(1, self.width())
        h = max(1, self.height())
        outline = (
            QColor(0, 0, 0, 12)
            if theme.base.lightnessF() > 0.6
            else QColor(255, 255, 255, 10)
        )

        for color, points in zip(theme.shard_colors, theme.shard_points, strict=False):
            path = QPainterPath()
            x0, y0 = points[0]
            path.moveTo(int(x0 * w), int(y0 * h))
            for x, y in points[1:]:
                path.lineTo(int(x * w), int(y * h))
            path.closeSubpath()
            painter.fillPath(path, color)
            painter.setPen(outline)
            painter.drawPath(path)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        self._paint_theme(painter, self._theme)
        painter.fillRect(
            self.rect(), QColor(0, 0, 0, self._darken_overlay_alpha(self._theme))
        )

        if self._theme_to is not None and self._theme_blend > 0.0:
            painter.save()
            painter.setOpacity(float(self._theme_blend))
            self._paint_theme(painter, self._theme_to)
            painter.fillRect(
                self.rect(), QColor(0, 0, 0, self._darken_overlay_alpha(self._theme_to))
            )
            painter.restore()
