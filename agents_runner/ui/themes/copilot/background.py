"""Copilot theme background rendering with animated code typing effect."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
    QStaticText,
)
from PySide6.QtWidgets import QWidget


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


def copilot_font_metrics(
    rect: QRect,
    font_cache: QFont | None,
    metrics_cache: QFontMetricsF | None,
    char_w_cache: float,
    line_h_cache: float,
) -> tuple[QFont, QFontMetricsF, float, float]:
    """Get or compute font metrics for Copilot theme code rendering."""
    if font_cache is None or metrics_cache is None:
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPixelSize(12 if rect.height() >= 920 else 11)
        metrics = QFontMetricsF(font)
        char_w = float(metrics.horizontalAdvance("M"))
        line_h = float(max(12.0, metrics.lineSpacing() * 1.15))

        return font, metrics, char_w, line_h

    return font_cache, metrics_cache, char_w_cache, line_h_cache


def ensure_copilot_sources(
    source_files: list[Path],
    repo_root: Path | None,
) -> tuple[list[Path], Path]:
    """Discover Python source files from repository for code snippets."""
    if source_files:
        return source_files, repo_root or Path.cwd()

    if repo_root is None:
        # From agents_runner/ui/themes/copilot/background.py, go up 4 levels to project root
        repo_root = Path(__file__).resolve().parents[4]

    root = repo_root
    candidates: list[Path] = []
    main_py = root / "main.py"
    if main_py.is_file():
        candidates.append(main_py)

    agents_dir = root / "agents_runner"
    if agents_dir.is_dir():
        candidates.extend(sorted(agents_dir.rglob("*.py")))

    source_files = [p for p in candidates if p.is_file()]
    return source_files, repo_root


def copilot_pick_snippet(
    rng: random.Random,
    source_files: list[Path],
) -> list[str]:
    """Pick a random code snippet from source files."""
    if not source_files:
        return []

    for _ in range(8):
        path = rng.choice(source_files)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        raw_lines = text.splitlines()
        if not raw_lines:
            continue

        start = int(rng.randrange(0, max(1, len(raw_lines))))
        span = int(rng.randint(8, 16))
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


def ensure_copilot_panes(
    rect: QRect,
    panes: list[_CopilotPane],
    rng: random.Random,
    source_files: list[Path],
) -> list[_CopilotPane]:
    """Ensure correct number of panes exist for current window size."""
    w, h = rect.width(), rect.height()
    if w < 80 or h < 80:
        return panes

    pane_count = 2 if w >= 980 else 1
    if len(panes) == pane_count:
        return panes

    new_panes: list[_CopilotPane] = []
    for _ in range(pane_count):
        pane = _CopilotPane(
            pending=[],
            active=None,
            lines=[],
            scroll_offset=0.0,
            cooldown_s=0.0,
        )
        copilot_fill_pending(pane, rng, source_files, min_lines=44)
        new_panes.append(pane)

    return new_panes


def copilot_fill_pending(
    pane: _CopilotPane,
    rng: random.Random,
    source_files: list[Path],
    *,
    min_lines: int,
) -> None:
    """Fill pending lines queue with code snippets."""
    attempts = 0
    while len(pane.pending) < min_lines and attempts < 14:
        pane.pending.extend(copilot_pick_snippet(rng, source_files))
        attempts += 1

    if not pane.pending:
        pane.pending.append("def hello_world() -> None:")
        pane.pending.append("    print('hello')  # fallback")


def copilot_pick_color(rng: random.Random) -> QColor:
    """Pick a random color for code line."""
    roll = float(rng.random())
    if roll < 0.84:
        return QColor(95, 237, 131, 220)  # neon green
    if roll < 0.93:
        return QColor(139, 148, 158, 180)  # gray
    if roll < 0.975:
        return QColor(192, 110, 255, 190)  # purple
    return QColor(225, 29, 72, 190)  # accent red


def copilot_pick_style(rng: random.Random) -> tuple[QColor, str | None]:
    """Pick a color and optional rich text tag for code line."""
    roll = float(rng.random())
    if roll < 0.86:
        return QColor(95, 237, 131, 230), None  # green
    if roll < 0.93:
        return QColor(139, 148, 158, 210), "dim"
    if roll < 0.975:
        return QColor(192, 110, 255, 220), "purple"
    return QColor(225, 29, 72, 220), "red"


def copilot_clamp_line(text: str, *, max_cols: int) -> str:
    """Clamp line to maximum column width."""
    max_cols = int(max(18, max_cols))
    if len(text) <= max_cols:
        return text
    if max_cols <= 6:
        return text[:max_cols]
    return text[: max_cols - 3] + "..."


def copilot_make_active_line(
    text: str,
    rng: random.Random,
    font: QFont,
    *,
    max_cols: int,
) -> _CopilotActiveLine:
    """Create an active typing line with potential typing mistakes."""
    color, rich_tag = copilot_pick_style(rng)
    prefix = f"[{rich_tag}]" if rich_tag is not None else ""
    suffix = "[/]" if rich_tag is not None else ""

    # Clamp the body so we always keep the rich markers intact when used.
    usable_cols = int(max_cols - len(prefix) - len(suffix))
    if usable_cols < 18:
        prefix = ""
        suffix = ""
        rich_tag = None
        usable_cols = int(max_cols)

    body = copilot_clamp_line(text, max_cols=usable_cols)
    final_text = f"{prefix}{body}{suffix}"
    draw_text = final_text

    mistake_trigger_at = -1
    backspace_target = 0
    if len(body) >= 22 and rng.random() < 0.11:
        prefix_len = len(prefix)
        mistake_at_body = int(rng.randint(6, min(len(body) - 8, 48)))
        mistake_len = int(rng.randint(1, 2))
        original = body[mistake_at_body : mistake_at_body + mistake_len]
        mutated_chars: list[str] = []
        for ch in original:
            if "a" <= ch <= "z":
                mutated_chars.append(chr(ord("a") + int(rng.randrange(0, 26))))
            elif "A" <= ch <= "Z":
                mutated_chars.append(chr(ord("A") + int(rng.randrange(0, 26))))
            elif "0" <= ch <= "9":
                mutated_chars.append(chr(ord("0") + int(rng.randrange(0, 10))))
            else:
                mutated_chars.append(rng.choice(["_", ".", " "]))
        mutated = "".join(mutated_chars)
        mutated_body = (
            body[:mistake_at_body] + mutated + body[mistake_at_body + mistake_len :]
        )
        draw_text = f"{prefix}{mutated_body}{suffix}"
        extra_after = int(rng.randint(1, 4))
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

    cps = float(rng.uniform(12.0, 17.0))
    backspace_cps = float(rng.uniform(22.0, 34.0))

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


def tick_copilot_typed_code(
    widget: QWidget,
    panes: list[_CopilotPane],
    rng: random.Random,
    source_files: list[Path],
    font: QFont,
    char_w: float,
    line_h: float,
    *,
    dt_s: float,
) -> None:
    """Update typing animation state for all panes."""
    if not panes:
        return

    pane_rects = copilot_pane_rects(widget, panes)

    for pane_idx, pane in enumerate(panes):
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
                    copilot_fill_pending(pane, rng, source_files, min_lines=36)
                if pane.pending:
                    pane_rect = pane_rects[min(pane_idx, len(pane_rects) - 1)]
                    usable_w = max(1.0, float(pane_rect.width() - 36.0))
                    max_cols = int(max(18.0, usable_w / float(char_w)))
                    pane.active = copilot_make_active_line(
                        pane.pending.pop(0),
                        rng,
                        font,
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
                and rng.random() < (0.08 * float(dt_s))
            ):
                active.pause_s = float(rng.uniform(1.6, 3.2))
                continue

            active.typed_chars_f += float(active.cps) * float(dt_s)
            if (
                active.mistake_trigger_at >= 0
                and active.typed_chars() >= active.mistake_trigger_at
            ):
                active.state = "backspacing"

            if active.typed_chars() >= len(active.draw_text):
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
                        hold_s=float(rng.uniform(26.0, 40.0)),
                        fade_s=float(rng.uniform(32.0, 48.0)),
                        color=QColor(active.color),
                    )
                )
                if len(pane.lines) > 54:
                    pane.lines = pane.lines[-54:]
                pane.active = None
                pane.cooldown_s = float(rng.uniform(0.22, 0.55))

        else:
            if rng.random() < (0.05 * float(dt_s)):
                active.pause_s = float(rng.uniform(0.9, 1.8))
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
                    active.static_text.prepare(font)
                except (AttributeError, TypeError):
                    pass

        rate = min(1.0, float(dt_s) * 10.0)
        pane.scroll_offset += (0.0 - pane.scroll_offset) * rate


def copilot_pane_rects(rect: QRect, panes: list[_CopilotPane]) -> list[QRectF]:
    """Calculate layout rectangles for code panes."""
    w = float(max(1, rect.width()))
    h = float(max(1, rect.height()))

    mx = float(max(28.0, min(110.0, w * 0.075)))
    my = float(max(34.0, min(140.0, h * 0.12)))
    usable = QRectF(mx, my, max(1.0, w - 2.0 * mx), max(1.0, h - 2.0 * my))

    if len(panes) <= 1:
        ww = usable.width() * 0.92
        xx = usable.x() + (usable.width() - ww) * 0.5
        return [QRectF(xx, usable.y(), ww, usable.height())]

    gap = float(max(22.0, w * 0.03))
    half = (usable.width() - gap) * 0.5
    left = QRectF(usable.x(), usable.y(), half, usable.height())
    right = QRectF(usable.x() + half + gap, usable.y(), half, usable.height())
    return [left, right]


def paint_copilot_background(
    painter: QPainter,
    rect: QRect,
    panes: list[_CopilotPane],
    font: QFont,
    char_w: float,
    line_h: float,
) -> None:
    """Render Copilot theme background with animated code panes."""
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

    painter.setFont(font)

    pane_rects = copilot_pane_rects(rect, panes)
    if len(pane_rects) != len(panes):
        # Pane count mismatch; caller should reinitialize panes
        painter.restore()
        return

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

    for pane, pane_rect in zip(panes, pane_rects, strict=False):
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
                fade = 1.0 - (float(line.age_s) - float(line.hold_s)) / float(
                    line.fade_s
                )
            fade = max(0.0, min(1.0, fade))
            fade *= (
                min(1.0, float(line.age_s) / float(fade_in_s))
                if line.age_s < fade_in_s
                else 1.0
            )

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


@dataclass
class _CopilotRuntime:
    rng: random.Random = field(default_factory=random.Random)
    panes: list[_CopilotPane] = field(default_factory=list)
    repo_root: Path | None = None
    source_files: list[Path] = field(default_factory=list)
    font: QFont | None = None
    metrics: QFontMetricsF | None = None
    char_w: float = 8.0
    line_h: float = 16.0
    tick_accum_s: float = 0.0


class _CopilotBackground:
    theme_name = "copilot"

    @staticmethod
    def base_color() -> QColor:
        return QColor(13, 17, 23)  # #0D1117

    @staticmethod
    def overlay_alpha() -> int:
        return 18

    @staticmethod
    def init_runtime(*, widget: QWidget) -> object:
        return _CopilotRuntime()

    @staticmethod
    def on_resize(*, runtime: object, widget: QWidget) -> None:
        if not isinstance(runtime, _CopilotRuntime):
            return
        runtime.metrics = None
        runtime.panes = []

    @staticmethod
    def tick(*, runtime: object, widget: QWidget, now_s: float, dt_s: float) -> bool:
        if not isinstance(runtime, _CopilotRuntime):
            return True

        runtime.tick_accum_s += float(dt_s)
        step_s = 0.05
        max_steps = 6
        steps = 0
        while runtime.tick_accum_s >= step_s and steps < max_steps:
            runtime.tick_accum_s -= step_s

            runtime.source_files, runtime.repo_root = ensure_copilot_sources(
                runtime.source_files,
                runtime.repo_root,
            )
            runtime.panes = ensure_copilot_panes(
                widget,
                runtime.panes,
                runtime.rng,
                runtime.source_files,
            )

            runtime.font, runtime.metrics, runtime.char_w, runtime.line_h = (
                copilot_font_metrics(
                    widget,
                    runtime.font,
                    runtime.metrics,
                    runtime.char_w,
                    runtime.line_h,
                )
            )

            tick_copilot_typed_code(
                widget,
                runtime.panes,
                runtime.rng,
                runtime.source_files,
                runtime.font,
                runtime.char_w,
                runtime.line_h,
                dt_s=step_s,
            )
            steps += 1

        return True

    @staticmethod
    def paint(*, painter: QPainter, rect: QRect, runtime: object) -> None:
        state = runtime if isinstance(runtime, _CopilotRuntime) else _CopilotRuntime()
        state.source_files, state.repo_root = ensure_copilot_sources(
            state.source_files, state.repo_root
        )
        state.panes = ensure_copilot_panes(
            rect, state.panes, state.rng, state.source_files
        )

        state.font, state.metrics, state.char_w, state.line_h = copilot_font_metrics(
            rect, state.font, state.metrics, state.char_w, state.line_h
        )

        pane_rects = copilot_pane_rects(rect, state.panes)
        if len(pane_rects) != len(state.panes):
            state.panes = []
            state.panes = ensure_copilot_panes(
                rect, state.panes, state.rng, state.source_files
            )

        paint_copilot_background(
            painter,
            rect,
            state.panes,
            state.font,
            state.char_w,
            state.line_h,
        )


BACKGROUND = _CopilotBackground()
