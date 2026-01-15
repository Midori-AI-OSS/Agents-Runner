from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QRectF,
    Property,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor
from PySide6.QtGui import QFont
from PySide6.QtGui import QFontDatabase
from PySide6.QtGui import QFontMetricsF
from PySide6.QtGui import QLinearGradient
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QPen
from PySide6.QtGui import QRadialGradient
from PySide6.QtGui import QResizeEvent
from PySide6.QtGui import QStaticText
from PySide6.QtWidgets import QWidget

from agents_runner.ui.themes.gemini import background as gemini_bg


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
    agent_cli = str(agent_cli or "codex").strip().lower()
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

    # codex / ChatGPT neutral
    return _AgentTheme(
        name="codex",
        base=QColor(12, 13, 15),
    )


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


@dataclass
class _CopilotRenderedLine:
    text: str
    static_text: QStaticText
    age_s: float
    hold_s: float
    fade_s: float
    color: QColor


@dataclass
class _CopilotActiveLine:
    final_text: str
    draw_text: str
    static_text: QStaticText
    typed_chars_f: float
    cps: float
    color: QColor
    rich_tag: str | None
    pause_s: float
    state: str  # "typing" | "backspacing"
    backspace_target: int
    backspace_cps: float
    mistake_trigger_at: int

    def typed_chars(self) -> int:
        return int(max(0.0, self.typed_chars_f))


@dataclass
class _CopilotPane:
    pending: list[str]
    active: _CopilotActiveLine | None
    lines: list[_CopilotRenderedLine]
    scroll_offset: float
    cooldown_s: float


class GlassRoot(QWidget):
    _CODEX_BOUNDARY_ANGLE_DEG: float = 15.0
    _CLAUDE_STEP_S: float = 0.06
    _CLAUDE_SEGMENT_LIFETIME_S: float = 90.0
    _CLAUDE_SEGMENT_FADE_IN_S: float = 1.8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

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

        self._claude_rng = random.Random()
        self._claude_tips: list[_ClaudeBranchTip] = []
        self._claude_segments: list[_ClaudeBranchSegment] = []
        self._claude_last_tick_s = time.monotonic()
        self._claude_tick_accum_s = 0.0
        self._claude_palette_phase = 0.0
        self._claude_next_reset_s = self._claude_last_tick_s + 0.5

        self._gemini_rng = random.Random()
        self._gemini_orbs: list[gemini_bg._GeminiChromaOrb] = []
        self._gemini_last_tick_s = time.monotonic()
        self._gemini_tick_accum_s = 0.0

        self._copilot_rng = random.Random()
        self._copilot_panes: list[_CopilotPane] = []
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

        now_s = time.monotonic()
        dt = now_s - self._claude_last_tick_s
        if dt > 0.0:
            self._claude_last_tick_s = now_s
            dt = min(dt, 0.25)
            if (
                self._theme.name == "claude"
                or (self._theme_to is not None and self._theme_to.name == "claude")
            ):
                self._claude_tick_accum_s += float(dt)
                step_s = float(self._CLAUDE_STEP_S)
                # Use fixed-timestep integration for smoother motion.
                max_steps = 8
                steps = 0
                while self._claude_tick_accum_s >= step_s and steps < max_steps:
                    self._claude_tick_accum_s -= step_s
                    self._tick_claude_tree(dt_s=step_s, now_s=now_s)
                    steps += 1

        dt_gemini = now_s - self._gemini_last_tick_s
        if dt_gemini > 0.0:
            self._gemini_last_tick_s = now_s
            dt_gemini = min(dt_gemini, 0.25)
            if (
                self._theme.name == "gemini"
                or (self._theme_to is not None and self._theme_to.name == "gemini")
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
            if (
                self._theme.name == "copilot"
                or (self._theme_to is not None and self._theme_to.name == "copilot")
            ):
                self._copilot_tick_accum_s += float(dt_copilot)
                step_s = 0.05
                max_steps = 6
                steps = 0
                while self._copilot_tick_accum_s >= step_s and steps < max_steps:
                    self._copilot_tick_accum_s -= step_s
                    self._tick_copilot_typed_code(dt_s=step_s)
                    steps += 1

        # Trigger repaint if using Codex / Claude theme
        if (
            self._theme.name in {"codex", "claude", "gemini", "copilot"}
            or (
                self._theme_to is not None
                and self._theme_to.name in {"codex", "claude", "gemini", "copilot"}
            )
        ):
            self.update()

    def _claude_palette(self) -> tuple[QColor, QColor, QColor, QColor]:
        """
        Warm dark palette blended between "browser dark" and "code" moods.
        Returns: (top, bottom, accent, accent_dim)
        """
        t = float(self._claude_palette_phase)
        top = self._blend_colors("#201D18", "#1B1612", t)
        bottom = self._blend_colors("#1A1815", "#141210", t)
        accent = self._blend_colors("#C15F3C", "#A14A2F", 0.35 + 0.25 * (1.0 - t))
        accent_dim = self._blend_colors("#C15F3C", "#A14A2F", 0.75)
        return top, bottom, accent, accent_dim

    def _ensure_claude_tree(self) -> None:
        if self._claude_tips:
            return
        w, h = self.width(), self.height()
        if w < 80 or h < 80:
            return
        self._reset_claude_tree(now_s=time.monotonic())

    def _reset_claude_tree(self, *, now_s: float) -> None:
        self._claude_tips = []

        w = float(max(1, self.width()))
        h = float(max(1, self.height()))
        if w < 80.0 or h < 80.0:
            return

        root_count = int(self._claude_rng.randint(1, 2))
        for _ in range(root_count):
            side = self._claude_rng.choice(("left", "right", "bottom", "top"))
            if side == "left":
                x = 0.0
                y = self._claude_rng.uniform(h * 0.12, h * 0.88)
                angle = self._claude_rng.uniform(-0.35, 0.35)
            elif side == "right":
                x = w
                y = self._claude_rng.uniform(h * 0.12, h * 0.88)
                angle = math.pi + self._claude_rng.uniform(-0.35, 0.35)
            elif side == "top":
                x = self._claude_rng.uniform(w * 0.18, w * 0.82)
                y = 0.0
                angle = (math.pi * 0.5) + self._claude_rng.uniform(-0.45, 0.45)
            else:
                x = self._claude_rng.uniform(w * 0.18, w * 0.82)
                y = h
                angle = -(math.pi * 0.5) + self._claude_rng.uniform(-0.45, 0.45)

            self._claude_tips.append(
                _ClaudeBranchTip(
                    x=float(x),
                    y=float(y),
                    angle=float(angle),
                    thickness=float(self._claude_rng.uniform(1.0, 1.8)),
                    depth=0,
                    speed=float(self._claude_rng.uniform(16.0, 24.0)),
                )
            )

        self._claude_next_reset_s = float(now_s) + float(
            self._claude_rng.uniform(55.0, 85.0)
        )

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

    def _paint_gemini_background(self, painter: QPainter, rect: QWidget) -> None:
        self._ensure_gemini_orbs()
        gemini_bg.paint_gemini_background(painter, rect, self._gemini_orbs)

    def _copilot_font_metrics(self) -> tuple[QFont, QFontMetricsF, float, float]:
        if self._copilot_font is None or self._copilot_metrics is None:
            font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            font.setStyleHint(QFont.StyleHint.Monospace)
            font.setPixelSize(12 if self.height() >= 920 else 11)
            metrics = QFontMetricsF(font)
            char_w = float(metrics.horizontalAdvance("M"))
            line_h = float(max(12.0, metrics.lineSpacing() * 1.15))

            self._copilot_font = font
            self._copilot_metrics = metrics
            self._copilot_char_w = char_w
            self._copilot_line_h = line_h

        return self._copilot_font, self._copilot_metrics, self._copilot_char_w, self._copilot_line_h

    def _ensure_copilot_sources(self) -> None:
        if self._copilot_source_files:
            return
        if self._copilot_repo_root is None:
            self._copilot_repo_root = Path(__file__).resolve().parents[2]

        root = self._copilot_repo_root
        candidates: list[Path] = []
        main_py = root / "main.py"
        if main_py.is_file():
            candidates.append(main_py)

        agents_dir = root / "agents_runner"
        if agents_dir.is_dir():
            candidates.extend(sorted(agents_dir.rglob("*.py")))

        self._copilot_source_files = [p for p in candidates if p.is_file()]

    def _copilot_pick_snippet(self) -> list[str]:
        self._ensure_copilot_sources()
        if not self._copilot_source_files:
            return []

        for _ in range(8):
            path = self._copilot_rng.choice(self._copilot_source_files)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            raw_lines = text.splitlines()
            if not raw_lines:
                continue

            start = int(self._copilot_rng.randrange(0, max(1, len(raw_lines))))
            span = int(self._copilot_rng.randint(8, 16))
            picked: list[str] = []
            for raw in raw_lines[start : start + span]:
                line = raw.rstrip().replace("\t", "    ")
                if not line.strip():
                    continue
                if len(line) > 116:
                    line = line[:113] + "..."
                picked.append(line)
                if len(picked) >= 10:
                    break
            if picked:
                return picked
        return []

    def _ensure_copilot_panes(self) -> None:
        w, h = self.width(), self.height()
        if w < 80 or h < 80:
            return

        pane_count = 2 if w >= 980 else 1
        if len(self._copilot_panes) == pane_count:
            return

        self._copilot_panes = []
        for _ in range(pane_count):
            pane = _CopilotPane(
                pending=[],
                active=None,
                lines=[],
                scroll_offset=0.0,
                cooldown_s=0.0,
            )
            self._copilot_fill_pending(pane, min_lines=44)
            self._copilot_panes.append(pane)

    def _copilot_fill_pending(self, pane: _CopilotPane, *, min_lines: int) -> None:
        attempts = 0
        while len(pane.pending) < min_lines and attempts < 14:
            pane.pending.extend(self._copilot_pick_snippet())
            attempts += 1

        if not pane.pending:
            pane.pending.append("def hello_world() -> None:")
            pane.pending.append("    print('hello')  # fallback")

    def _copilot_pick_color(self) -> QColor:
        roll = float(self._copilot_rng.random())
        if roll < 0.84:
            return QColor(95, 237, 131, 220)  # neon green
        if roll < 0.93:
            return QColor(139, 148, 158, 180)  # gray
        if roll < 0.975:
            return QColor(192, 110, 255, 190)  # purple
        return QColor(225, 29, 72, 190)  # accent red

    def _copilot_pick_style(self) -> tuple[QColor, str | None]:
        roll = float(self._copilot_rng.random())
        if roll < 0.86:
            return QColor(95, 237, 131, 230), None  # green
        if roll < 0.93:
            return QColor(139, 148, 158, 210), "dim"
        if roll < 0.975:
            return QColor(192, 110, 255, 220), "purple"
        return QColor(225, 29, 72, 220), "red"

    @staticmethod
    def _copilot_clamp_line(text: str, *, max_cols: int) -> str:
        max_cols = int(max(18, max_cols))
        if len(text) <= max_cols:
            return text
        if max_cols <= 6:
            return text[:max_cols]
        return text[: max_cols - 3] + "..."

    def _copilot_make_active_line(self, text: str, *, max_cols: int) -> _CopilotActiveLine:
        font, _, _, _ = self._copilot_font_metrics()

        color, rich_tag = self._copilot_pick_style()
        prefix = f"[{rich_tag}]" if rich_tag is not None else ""
        suffix = "[/]" if rich_tag is not None else ""

        # Clamp the body so we always keep the rich markers intact when used.
        usable_cols = int(max_cols - len(prefix) - len(suffix))
        if usable_cols < 18:
            prefix = ""
            suffix = ""
            rich_tag = None
            usable_cols = int(max_cols)

        body = self._copilot_clamp_line(text, max_cols=usable_cols)
        final_text = f"{prefix}{body}{suffix}"
        draw_text = final_text

        mistake_trigger_at = -1
        backspace_target = 0
        if len(body) >= 22 and self._copilot_rng.random() < 0.11:
            prefix_len = len(prefix)
            mistake_at_body = int(self._copilot_rng.randint(6, min(len(body) - 8, 48)))
            mistake_len = int(self._copilot_rng.randint(1, 2))
            original = body[mistake_at_body : mistake_at_body + mistake_len]
            mutated_chars: list[str] = []
            for ch in original:
                if "a" <= ch <= "z":
                    mutated_chars.append(chr(ord("a") + int(self._copilot_rng.randrange(0, 26))))
                elif "A" <= ch <= "Z":
                    mutated_chars.append(chr(ord("A") + int(self._copilot_rng.randrange(0, 26))))
                elif "0" <= ch <= "9":
                    mutated_chars.append(chr(ord("0") + int(self._copilot_rng.randrange(0, 10))))
                else:
                    mutated_chars.append(self._copilot_rng.choice(["_", ".", " "]))
            mutated = "".join(mutated_chars)
            mutated_body = body[:mistake_at_body] + mutated + body[mistake_at_body + mistake_len :]
            draw_text = f"{prefix}{mutated_body}{suffix}"
            extra_after = int(self._copilot_rng.randint(1, 4))
            trigger = min(
                len(draw_text) - 1,
                prefix_len + mistake_at_body + mistake_len + extra_after,
            )
            backspace_target = prefix_len + mistake_at_body
            if trigger > backspace_target and trigger < len(draw_text) - 1:
                mistake_trigger_at = trigger
            else:
                draw_text = final_text

        static_text = QStaticText(draw_text)
        static_text.setTextFormat(Qt.TextFormat.PlainText)

        cps = float(self._copilot_rng.uniform(12.0, 17.0))
        backspace_cps = float(self._copilot_rng.uniform(22.0, 34.0))

        try:
            static_text.prepare(font)
        except (AttributeError, TypeError):
            pass

        return _CopilotActiveLine(
            final_text=str(final_text),
            draw_text=str(draw_text),
            static_text=static_text,
            typed_chars_f=0.0,
            cps=cps,
            color=QColor(color),
            rich_tag=None if rich_tag is None else str(rich_tag),
            pause_s=0.0,
            state="typing",
            backspace_target=int(backspace_target),
            backspace_cps=backspace_cps,
            mistake_trigger_at=int(mistake_trigger_at),
        )

    def _tick_copilot_typed_code(self, *, dt_s: float) -> None:
        self._ensure_copilot_panes()
        if not self._copilot_panes:
            return

        _, _, char_w, line_h = self._copilot_font_metrics()
        pane_rects = self._copilot_pane_rects(self)

        for pane_idx, pane in enumerate(self._copilot_panes):
            pane.cooldown_s = float(max(0.0, pane.cooldown_s - float(dt_s)))
            for line in pane.lines:
                line.age_s += float(dt_s)

            pane.lines = [
                line
                for line in pane.lines
                if line.age_s <= float(line.hold_s + line.fade_s)
            ]

            if pane.active is None:
                if pane.cooldown_s <= 0.0:
                    if not pane.pending:
                        self._copilot_fill_pending(pane, min_lines=36)
                    if pane.pending:
                        pane_rect = pane_rects[min(pane_idx, len(pane_rects) - 1)]
                        usable_w = max(1.0, float(pane_rect.width() - 36.0))
                        max_cols = int(max(18.0, usable_w / float(char_w)))
                        pane.active = self._copilot_make_active_line(
                            pane.pending.pop(0),
                            max_cols=max_cols,
                        )

            active = pane.active
            if active is None:
                pass
            elif active.pause_s > 0.0:
                active.pause_s = float(max(0.0, active.pause_s - float(dt_s)))
            elif active.state == "typing":
                typed_now = active.typed_chars()
                if (
                    typed_now >= 4
                    and typed_now < len(active.draw_text) - 6
                    and self._copilot_rng.random() < (0.08 * float(dt_s))
                ):
                    active.pause_s = float(self._copilot_rng.uniform(1.6, 3.2))
                    continue

                active.typed_chars_f += float(active.cps) * float(dt_s)
                if active.mistake_trigger_at >= 0 and active.typed_chars() >= active.mistake_trigger_at:
                    active.state = "backspacing"

                if active.typed_chars() >= len(active.draw_text):
                    font, _, _, _ = self._copilot_font_metrics()
                    static_text = QStaticText(active.final_text)
                    static_text.setTextFormat(Qt.TextFormat.PlainText)
                    try:
                        static_text.prepare(font)
                    except (AttributeError, TypeError):
                        pass

                    pane.lines.append(
                        _CopilotRenderedLine(
                            text=active.final_text,
                            static_text=static_text,
                            age_s=0.0,
                            hold_s=float(self._copilot_rng.uniform(26.0, 40.0)),
                            fade_s=float(self._copilot_rng.uniform(32.0, 48.0)),
                            color=QColor(active.color),
                        )
                    )
                    if len(pane.lines) > 54:
                        pane.lines = pane.lines[-54:]
                    pane.active = None
                    pane.cooldown_s = float(self._copilot_rng.uniform(0.22, 0.55))

            else:
                if self._copilot_rng.random() < (0.05 * float(dt_s)):
                    active.pause_s = float(self._copilot_rng.uniform(0.9, 1.8))
                    continue
                active.typed_chars_f -= float(active.backspace_cps) * float(dt_s)
                if active.typed_chars() <= active.backspace_target:
                    active.typed_chars_f = float(active.backspace_target)
                    active.state = "typing"
                    active.mistake_trigger_at = -1
                    active.draw_text = active.final_text
                    active.static_text = QStaticText(active.draw_text)
                    active.static_text.setTextFormat(Qt.TextFormat.PlainText)
                    try:
                        font, _, _, _ = self._copilot_font_metrics()
                        active.static_text.prepare(font)
                    except (AttributeError, TypeError):
                        pass

            rate = min(1.0, float(dt_s) * 10.0)
            pane.scroll_offset += (0.0 - pane.scroll_offset) * rate

    def _copilot_pane_rects(self, rect: QWidget) -> list[QRectF]:
        w = float(max(1, rect.width()))
        h = float(max(1, rect.height()))

        mx = float(max(28.0, min(110.0, w * 0.075)))
        my = float(max(34.0, min(140.0, h * 0.12)))
        usable = QRectF(mx, my, max(1.0, w - 2.0 * mx), max(1.0, h - 2.0 * my))

        if len(self._copilot_panes) <= 1:
            ww = usable.width() * 0.92
            xx = usable.x() + (usable.width() - ww) * 0.5
            return [QRectF(xx, usable.y(), ww, usable.height())]

        gap = float(max(22.0, w * 0.03))
        half = (usable.width() - gap) * 0.5
        left = QRectF(usable.x(), usable.y(), half, usable.height())
        right = QRectF(usable.x() + half + gap, usable.y(), half, usable.height())
        return [left, right]

    def _paint_copilot_background(self, painter: QPainter, rect: QWidget) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = int(rect.width())
        h = int(rect.height())
        if w <= 0 or h <= 0:
            painter.restore()
            return

        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor("#101826"))
        base.setColorAt(0.55, QColor("#0D1117"))
        base.setColorAt(1.0, QColor("#0B0F14"))
        painter.fillRect(rect, base)

        self._ensure_copilot_panes()
        font, _, char_w, line_h = self._copilot_font_metrics()
        painter.setFont(font)

        pane_rects = self._copilot_pane_rects(rect)
        if len(pane_rects) != len(self._copilot_panes):
            # Pane count can change across resizes; keep the visuals stable.
            self._copilot_panes = []
            self._ensure_copilot_panes()
            pane_rects = self._copilot_pane_rects(rect)

        for pane_rect in pane_rects:
            center = QPointF(pane_rect.center())
            radius = float(max(pane_rect.width(), pane_rect.height()) * 0.68)
            glow = QRadialGradient(center, radius)
            glow.setColorAt(0.0, QColor(255, 255, 255, 10))
            glow.setColorAt(0.55, QColor(255, 255, 255, 5))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.fillRect(pane_rect, glow)

        painter.setRenderHint(QPainter.TextAntialiasing, True)
        fade_in_s = 0.22

        for pane, pane_rect in zip(self._copilot_panes, pane_rects, strict=False):
            painter.save()
            painter.setClipRect(pane_rect)

            x = float(pane_rect.x() + 18.0)
            y_bottom = float(pane_rect.y() + pane_rect.height() - 18.0)
            max_lines = int(max(6.0, (pane_rect.height() - 36.0) / float(line_h)))
            y0 = y_bottom - float(line_h)

            visible_lines = pane.lines[-max_lines:]
            for idx, line in enumerate(reversed(visible_lines)):
                if line.fade_s <= 0.01:
                    continue

                fade = 1.0
                if line.age_s >= line.hold_s:
                    fade = 1.0 - (float(line.age_s) - float(line.hold_s)) / float(line.fade_s)
                fade = max(0.0, min(1.0, fade))
                fade *= min(1.0, float(line.age_s) / float(fade_in_s)) if line.age_s < fade_in_s else 1.0

                if fade <= 0.0:
                    continue

                y = y0 - float(idx) * float(line_h)
                if y < pane_rect.y() - float(line_h):
                    continue

                c = QColor(line.color)
                c.setAlpha(int(c.alpha() * fade))
                painter.setPen(c)
                painter.drawStaticText(QPointF(x, y), line.static_text)

            active = pane.active
            if active is not None:
                typed = min(len(active.draw_text), active.typed_chars())
                y = y_bottom
                c = QColor(active.color)
                painter.setPen(c)

                clip_w = float(char_w) * float(typed)
                painter.save()
                painter.setClipRect(QRectF(x, y, clip_w, float(line_h) * 1.4))
                painter.drawStaticText(QPointF(x, y), active.static_text)
                painter.restore()

                blink = (time.monotonic() % 1.1) < 0.62
                if blink:
                    cursor_x = x + float(char_w) * float(typed)
                    cursor_color = QColor(active.color)
                    cursor_color.setAlpha(min(255, int(cursor_color.alpha() * 0.85)))
                    cursor_pen = QPen(cursor_color, 1.0)
                    painter.save()
                    painter.setPen(cursor_pen)
                    painter.drawLine(
                        QPointF(cursor_x, y + 1.0),
                        QPointF(cursor_x, y + float(line_h) * 0.92),
                    )
                    painter.restore()

            painter.restore()

        vignette = QRadialGradient(QPointF(w * 0.55, h * 0.45), float(max(w, h) * 0.92))
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 56))
        painter.fillRect(rect, vignette)

        painter.restore()

    def _tick_claude_tree(self, *, dt_s: float, now_s: float) -> None:
        self._claude_palette_phase = (1.0 + math.sin(time.time() / 240.0 * 2.0 * math.pi)) * 0.5

        w = float(max(1, self.width()))
        h = float(max(1, self.height()))
        if w < 80.0 or h < 80.0:
            return

        if not self._claude_tips or now_s >= self._claude_next_reset_s:
            self._reset_claude_tree(now_s=now_s)

        for seg in self._claude_segments:
            seg.age_s += float(dt_s)

        max_age_s = float(self._CLAUDE_SEGMENT_LIFETIME_S)
        self._claude_segments = [s for s in self._claude_segments if s.age_s <= max_age_s]

        tips_next: list[_ClaudeBranchTip] = []
        max_tips = 14
        max_depth = 180

        for tip in self._claude_tips:
            if tip.depth > max_depth or tip.thickness < 0.55:
                continue

            if self._claude_rng.random() < (0.020 * dt_s) and tip.depth >= 10:
                continue

            step = tip.speed * dt_s
            if step <= 0.1:
                tips_next.append(tip)
                continue

            # Apply a small dt-scaled drift to avoid visible "jumps" in direction.
            drift = self._claude_rng.uniform(-0.28, 0.28) * dt_s
            angle = tip.angle + drift
            nx = tip.x + math.cos(angle) * step
            ny = tip.y + math.sin(angle) * step

            # Keep growth loosely contained inside the viewport with a small buffer.
            if nx < -40.0 or nx > w + 40.0 or ny < -40.0 or ny > h + 40.0:
                continue

            roll = self._claude_rng.random()
            tone = 0 if roll < 0.68 else (1 if roll < 0.90 else 2)
            self._claude_segments.append(
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
                thickness=float(tip.thickness * self._claude_rng.uniform(0.985, 0.997)),
                depth=int(tip.depth + 1),
                speed=float(tip.speed * self._claude_rng.uniform(0.985, 1.01)),
            )

            if len(tips_next) < max_tips:
                tips_next.append(next_tip)

            if len(tips_next) < max_tips and tip.depth >= 2:
                branch_chance = 0.065 * dt_s
                if self._claude_rng.random() < branch_chance:
                    spread = self._claude_rng.uniform(0.28, 0.72)
                    sign = -1.0 if self._claude_rng.random() < 0.5 else 1.0
                    tips_next.append(
                        _ClaudeBranchTip(
                            x=float(nx),
                            y=float(ny),
                            angle=float(angle + sign * spread),
                            thickness=float(tip.thickness * self._claude_rng.uniform(0.78, 0.92)),
                            depth=int(tip.depth + 1),
                            speed=float(tip.speed * self._claude_rng.uniform(0.90, 1.05)),
                        )
                    )

        self._claude_tips = tips_next
        if len(self._claude_segments) > 900:
            self._claude_segments = self._claude_segments[-900:]

    def _paint_claude_background(self, painter: QPainter, rect: QWidget) -> None:
        w = int(rect.width())
        h = int(rect.height())
        if w <= 0 or h <= 0:
            return

        self._ensure_claude_tree()
        top, bottom, accent, accent_dim = self._claude_palette()

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, top)
        grad.setColorAt(0.55, self._blend_colors(top, bottom, 0.55))
        grad.setColorAt(1.0, bottom)
        painter.fillRect(0, 0, w, h, grad)

        vignette = QRadialGradient(QPointF(w * 0.5, h * 0.5), float(max(w, h)) * 0.75)
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 44))
        painter.fillRect(0, 0, w, h, vignette)

        if not self._claude_segments:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        max_age_s = float(self._CLAUDE_SEGMENT_LIFETIME_S)
        for seg in self._claude_segments:
            t = max(0.0, min(1.0, float(seg.age_s) / max_age_s))
            fade_out = 1.0 - t
            fade_in = min(1.0, float(seg.age_s) / float(self._CLAUDE_SEGMENT_FADE_IN_S))
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

    def _paint_theme(self, painter: QPainter, theme: _AgentTheme) -> None:
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
