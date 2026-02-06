from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QRect,
    Property,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor
from PySide6.QtGui import QFont
from PySide6.QtGui import QFontMetricsF
from PySide6.QtGui import QLinearGradient
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget

from agents_runner.ui.themes.claude import background as claude_bg
from agents_runner.ui.themes.codex import background as codex_bg
from agents_runner.ui.themes.copilot import background as copilot_bg
from agents_runner.ui.themes.gemini import background as gemini_bg
from agents_runner.ui.themes.midoriai import background as midoriai_bg


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


def _theme_for_agent(agent_cli: str) -> _AgentTheme:
    agent_cli = str(agent_cli or "midoriai").strip().lower()
    if agent_cli == "copilot":
        return _AgentTheme(
            name="copilot",
            base=QColor(13, 17, 23),  # #0D1117
        )
    if agent_cli == "claude":
        return _AgentTheme(
            name="claude",
            base=QColor(245, 245, 240),  # #F5F5F0
        )
    if agent_cli == "gemini":
        return _AgentTheme(
            name="gemini",
            base=QColor(18, 20, 28),  # #12141C (avoid white flash)
        )
    if agent_cli == "codex":
        return _AgentTheme(
            name="codex",
            base=QColor(12, 13, 15),
        )

    # midoriai neutral / default fallback
    return _AgentTheme(
        name="midoriai",
        base=QColor(10, 11, 13),
    )


class GlassRoot(QWidget):
    _CLAUDE_STEP_S: float = 0.06

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._theme = _theme_for_agent("midoriai")
        self._theme_to: _AgentTheme | None = None
        self._theme_blend = 0.0
        self._theme_anim: QPropertyAnimation | None = None

        # Midori AI background animation phase parameters (reuses Codex logic)
        self._midoriai_split_ratio: float = 0.45
        self._midoriai_color_blend_phase_top: float = 0.0
        self._midoriai_color_blend_phase_bottom: float = 0.0

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

        self._claude_rng = random.Random()
        self._claude_tips: list[claude_bg._ClaudeBranchTip] = []
        self._claude_segments: list[claude_bg._ClaudeBranchSegment] = []
        self._claude_last_tick_s = time.monotonic()
        self._claude_tick_accum_s = 0.0
        self._claude_palette_phase = 0.0
        self._claude_next_reset_s = self._claude_last_tick_s + 0.5

        self._gemini_rng = random.Random()
        self._gemini_orbs: list[gemini_bg._GeminiChromaOrb] = []
        self._gemini_last_tick_s = time.monotonic()
        self._gemini_tick_accum_s = 0.0

        self._copilot_rng = random.Random()
        self._copilot_panes: list[copilot_bg._CopilotPane] = []
        self._copilot_last_tick_s = time.monotonic()
        self._copilot_tick_accum_s = 0.0
        self._copilot_repo_root: Path | None = None
        self._copilot_source_files: list[Path] = []
        self._copilot_font: QFont | None = None
        self._copilot_metrics: QFontMetricsF | None = None
        self._copilot_char_w: float = 8.0
        self._copilot_line_h: float = 16.0

        # Start Codex background animation timer
        codex_timer = QTimer(self)
        codex_timer.setInterval(100)
        codex_timer.timeout.connect(self._update_background_animation)
        codex_timer.start()

    @staticmethod
    def _darken_overlay_alpha(theme: _AgentTheme) -> int:
        if theme.name == "midoriai":
            return 32
        if theme.name == "codex":
            return 28
        if theme.name == "claude":
            return 22
        if theme.name in {"copilot", "gemini"}:
            return 18
        lightness = float(theme.base.lightnessF())
        # Keep the background readable without crushing the palette into near-black.
        # Slightly stronger darkening on light themes, lighter on dark themes.
        alpha = int(165 + 55 * lightness)
        return int(min(max(alpha, 0), 255))

    def set_agent_theme(self, agent_cli: str) -> None:
        theme = _theme_for_agent(agent_cli)
        if theme.name == self._theme.name:
            return

        if theme.name == "claude":
            self._claude_next_reset_s = time.monotonic()
        if theme.name == "gemini":
            self._gemini_tick_accum_s = 0.0
            self._gemini_last_tick_s = time.monotonic()
        if theme.name == "copilot":
            self._copilot_tick_accum_s = 0.0
            self._copilot_last_tick_s = time.monotonic()
            self._copilot_panes = []

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
        self._copilot_metrics = None
        if self._theme.name == "claude" or (
            self._theme_to is not None and self._theme_to.name == "claude"
        ):
            self._claude_next_reset_s = time.monotonic()
        if self._theme.name == "gemini" or (
            self._theme_to is not None and self._theme_to.name == "gemini"
        ):
            self._constrain_gemini_orbs()
        if self._theme.name == "copilot" or (
            self._theme_to is not None and self._theme_to.name == "copilot"
        ):
            self._copilot_panes = []

    def _get_theme_blend(self) -> float:
        return float(self._theme_blend)

    def _set_theme_blend(self, value: float) -> None:
        self._theme_blend = float(min(max(value, 0.0), 1.0))
        self.update()

    themeBlend = Property(float, _get_theme_blend, _set_theme_blend)

    def _update_background_animation(self) -> None:
        """Update Codex and Midori AI background animation phase parameters."""
        self._codex_split_ratio = codex_bg.calc_split_ratio()
        self._codex_color_blend_phase_top = codex_bg.calc_top_phase()
        self._codex_color_blend_phase_bottom = codex_bg.calc_bottom_phase()

        self._midoriai_split_ratio = midoriai_bg.calc_split_ratio()
        self._midoriai_color_blend_phase_top = midoriai_bg.calc_top_phase()
        self._midoriai_color_blend_phase_bottom = midoriai_bg.calc_bottom_phase()

        now_s = time.monotonic()
        dt = now_s - self._claude_last_tick_s
        if dt > 0.0:
            self._claude_last_tick_s = now_s
            dt = min(dt, 0.25)
            if self._theme.name == "claude" or (
                self._theme_to is not None and self._theme_to.name == "claude"
            ):
                self._claude_tick_accum_s += float(dt)
                step_s = float(self._CLAUDE_STEP_S)
                # Use fixed-timestep integration for smoother motion.
                max_steps = 8
                steps = 0
                while self._claude_tick_accum_s >= step_s and steps < max_steps:
                    self._claude_tick_accum_s -= step_s
                    (
                        self._claude_tips,
                        self._claude_segments,
                        self._claude_palette_phase,
                        self._claude_next_reset_s,
                    ) = claude_bg.tick_claude_tree(
                        self._claude_tips,
                        self._claude_segments,
                        self._claude_rng,
                        self.width(),
                        self.height(),
                        self._claude_next_reset_s,
                        dt_s=step_s,
                        now_s=now_s,
                    )
                    steps += 1

        dt_gemini = now_s - self._gemini_last_tick_s
        if dt_gemini > 0.0:
            self._gemini_last_tick_s = now_s
            dt_gemini = min(dt_gemini, 0.25)
            if self._theme.name == "gemini" or (
                self._theme_to is not None and self._theme_to.name == "gemini"
            ):
                self._gemini_tick_accum_s += float(dt_gemini)
                step_s = 0.05
                max_steps = 6
                steps = 0
                while self._gemini_tick_accum_s >= step_s and steps < max_steps:
                    self._gemini_tick_accum_s -= step_s
                    self._tick_gemini_chroma_orbs(dt_s=step_s)
                    steps += 1

        dt_copilot = now_s - self._copilot_last_tick_s
        if dt_copilot > 0.0:
            self._copilot_last_tick_s = now_s
            dt_copilot = min(dt_copilot, 0.25)
            if self._theme.name == "copilot" or (
                self._theme_to is not None and self._theme_to.name == "copilot"
            ):
                self._copilot_tick_accum_s += float(dt_copilot)
                step_s = 0.05
                max_steps = 6
                steps = 0
                while self._copilot_tick_accum_s >= step_s and steps < max_steps:
                    self._copilot_tick_accum_s -= step_s
                    self._tick_copilot_typed_code(dt_s=step_s)
                    steps += 1

        # Trigger repaint if using Codex / Midori AI / Claude / Gemini / Copilot theme
        if self._theme.name in {"codex", "midoriai", "claude", "gemini", "copilot"} or (
            self._theme_to is not None
            and self._theme_to.name
            in {"codex", "midoriai", "claude", "gemini", "copilot"}
        ):
            self.update()

    def _ensure_gemini_orbs(self) -> None:
        self._gemini_orbs = gemini_bg.ensure_gemini_orbs(
            self._gemini_orbs,
            self._gemini_rng,
            self.width(),
            self.height(),
        )

    def _constrain_gemini_orbs(self) -> None:
        gemini_bg.constrain_gemini_orbs(
            self._gemini_orbs,
            self.width(),
            self.height(),
        )

    def _tick_gemini_chroma_orbs(self, *, dt_s: float) -> None:
        self._ensure_gemini_orbs()
        gemini_bg.tick_gemini_chroma_orbs(
            self._gemini_orbs,
            self._gemini_rng,
            self.width(),
            self.height(),
            dt_s,
        )

    def _paint_gemini_background(self, painter: QPainter, rect: QRect) -> None:
        self._ensure_gemini_orbs()
        gemini_bg.paint_gemini_background(painter, rect, self._gemini_orbs)

    def _copilot_font_metrics(self) -> tuple[QFont, QFontMetricsF, float, float]:
        font, metrics, char_w, line_h = copilot_bg.copilot_font_metrics(
            self,
            self._copilot_font,
            self._copilot_metrics,
            self._copilot_char_w,
            self._copilot_line_h,
        )
        self._copilot_font = font
        self._copilot_metrics = metrics
        self._copilot_char_w = char_w
        self._copilot_line_h = line_h
        return font, metrics, char_w, line_h

    def _ensure_copilot_sources(self) -> None:
        self._copilot_source_files, self._copilot_repo_root = (
            copilot_bg.ensure_copilot_sources(
                self._copilot_source_files,
                self._copilot_repo_root,
            )
        )

    def _ensure_copilot_panes(self) -> None:
        self._ensure_copilot_sources()
        self._copilot_panes = copilot_bg.ensure_copilot_panes(
            self,
            self._copilot_panes,
            self._copilot_rng,
            self._copilot_source_files,
        )

    def _tick_copilot_typed_code(self, *, dt_s: float) -> None:
        self._ensure_copilot_panes()
        if not self._copilot_panes:
            return

        font, _, char_w, line_h = self._copilot_font_metrics()
        copilot_bg.tick_copilot_typed_code(
            self,
            self._copilot_panes,
            self._copilot_rng,
            self._copilot_source_files,
            font,
            char_w,
            line_h,
            dt_s=dt_s,
        )

    def _paint_copilot_background(self, painter: QPainter, rect: QRect) -> None:
        self._ensure_copilot_panes()
        font, _, char_w, line_h = self._copilot_font_metrics()

        pane_rects = copilot_bg.copilot_pane_rects(rect, self._copilot_panes)
        if len(pane_rects) != len(self._copilot_panes):
            # Pane count can change across resizes; keep the visuals stable.
            self._copilot_panes = []
            self._ensure_copilot_panes()

        copilot_bg.paint_copilot_background(
            painter,
            rect,
            self._copilot_panes,
            font,
            char_w,
            line_h,
        )

    def _paint_claude_background(self, painter: QPainter, rect: QRect) -> None:
        self._claude_tips, self._claude_next_reset_s = (
            claude_bg.paint_claude_background(
                painter,
                rect,
                self._claude_tips,
                self._claude_segments,
                self._claude_rng,
                self._claude_palette_phase,
                self.width(),
                self.height(),
                time.monotonic(),
                codex_bg.blend_colors,
            )
        )

    def _paint_codex_background(self, painter: QPainter, rect: QRect) -> None:
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
        (
            self._cached_top_color,
            self._cached_top_phase,
            self._cached_bottom_color,
            self._cached_bottom_phase,
        ) = codex_bg.paint_codex_background(
            painter,
            rect,
            self._codex_split_ratio,
            self._codex_color_blend_phase_top,
            self._codex_color_blend_phase_bottom,
            self._cached_top_color,
            self._cached_top_phase,
            self._cached_bottom_color,
            self._cached_bottom_phase,
        )

    def _paint_midoriai_background(self, painter: QPainter, rect: QRect) -> None:
        """
        Paint the two-band background composition for Midori AI theme.

        Renders animated background with:
        - Top band: Darker blue to teal gradient
        - Bottom band: Darker accent gradient
        - Soft feathered diagonal boundary between bands
        - Large soft color blobs overlay
        - Extra dark overlay for deeper appearance

        Args:
            painter: QPainter instance to draw with
            rect: Rectangle defining the paint area
        """
        # Use cached phase values (updated by timer)
        (
            self._cached_top_color,
            self._cached_top_phase,
            self._cached_bottom_color,
            self._cached_bottom_phase,
        ) = midoriai_bg.paint_midoriai_background(
            painter,
            rect,
            self._midoriai_split_ratio,
            self._midoriai_color_blend_phase_top,
            self._midoriai_color_blend_phase_bottom,
            self._cached_top_color,
            self._cached_top_phase,
            self._cached_bottom_color,
            self._cached_bottom_phase,
        )

    def _paint_theme(self, painter: QPainter, theme: _AgentTheme) -> None:
        if theme.name == "midoriai":
            self._paint_midoriai_background(painter, self.rect())
            return
        if theme.name == "codex":
            self._paint_codex_background(painter, self.rect())
            return
        if theme.name == "claude":
            self._paint_claude_background(painter, self.rect())
            return
        if theme.name == "gemini":
            self._paint_gemini_background(painter, self.rect())
            return
        if theme.name == "copilot":
            self._paint_copilot_background(painter, self.rect())
            return

        # Fallback for any unknown themes
        painter.fillRect(self.rect(), theme.base)

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
