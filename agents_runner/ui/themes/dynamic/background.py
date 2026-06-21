"""Dynamic theme background that adapts to radio art colors."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass
from dataclasses import field

from PySide6.QtCore import QPointF
from PySide6.QtCore import QRect
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QRadialGradient
from PySide6.QtWidgets import QWidget

from agents_runner.ui.themes.midori_variant import (  # pyright: ignore[reportPrivateUsage]
    MidoriVariantSpec,
    _apply_base_gradient,
    _blend,
    _build_blob_seeds,
    _paint_blobs as _midori_paint_blobs,
)

_lock = threading.Lock()
_current_spec: MidoriVariantSpec | None = None
_previous_spec: MidoriVariantSpec | None = None
_current_style: str = "blobs"
_transition_start_s: float | None = None
_transition_duration: float = 2.0

_FALLBACK_SPEC = MidoriVariantSpec(
    theme_name="dynamic",
    base_color=QColor(9, 8, 17),
    overlay_alpha=30,
    top_start=QColor("#2A2F8E"),
    top_end=QColor("#652E93"),
    bottom_start=QColor("#341E4B"),
    bottom_end=QColor("#A5532C"),
    blob_palette=(
        QColor(118, 106, 255, 208),
        QColor(176, 108, 255, 190),
        QColor(255, 164, 72, 194),
        QColor(255, 122, 86, 182),
        QColor(105, 184, 255, 168),
        QColor(232, 136, 255, 165),
    ),
    ambient_overlay=QColor(0, 0, 0, 34),
    boundary_angle_deg=17.0,
    motion_speed=1.22,
    wave_strength=0.42,
    pulse_strength=0.44,
    light_mode=False,
)


def set_art_spec(spec: MidoriVariantSpec | None, style: str) -> None:
    """Set the current art-derived spec and style for the dynamic background."""
    with _lock:
        global _current_spec, _previous_spec, _current_style, _transition_start_s
        _previous_spec = _current_spec
        _current_spec = spec
        _current_style = style
        _transition_start_s = time.monotonic()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class _DynamicRuntime:
    barcode_bars: list[float] = field(default_factory=lambda: [0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9])
    barcode_directions: list[float] = field(default_factory=lambda: [0.02, -0.015, 0.01, -0.02, 0.015, -0.01, 0.018])
    orb_positions: list[tuple[float, float]] = field(
        default_factory=lambda: [
            (0.2, 0.3),
            (0.7, 0.4),
            (0.4, 0.65),
            (0.8, 0.75),
            (0.15, 0.7),
            (0.55, 0.2),
        ]
    )
    orb_phases: list[float] = field(default_factory=lambda: [0.0, 1.5, 3.0, 4.5, 2.0, 5.5])
    orb_base_radius: float = 0.0
    tick_time: float = 0.0
    width: int = 0
    height: int = 0
    pulse_phase: float = 0.0
    wave_phase: float = 0.0
    blobs: tuple[object, ...] = ()
    rng: random.Random = field(default_factory=random.Random)
    top_phase: float = 0.0
    bottom_phase: float = 0.0
    split_ratio: float = 0.45


def _paint_barcode(
    *,
    painter: QPainter,
    rect: QRect,
    runtime: _DynamicRuntime,
    spec: MidoriVariantSpec,
    blend_factor: float,
) -> None:
    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0:
        return

    palette = (
        spec.top_start,
        spec.top_end,
        spec.bottom_start,
        spec.bottom_end,
    )
    bar_count = len(runtime.barcode_bars)
    if bar_count == 0:
        return

    bar_w = max(1, int(w * 0.04))

    with _lock:
        prev_spec = _previous_spec

    prev_palette = None
    if prev_spec is not None and blend_factor < 1.0:
        prev_palette = (
            prev_spec.top_start,
            prev_spec.top_end,
            prev_spec.bottom_start,
            prev_spec.bottom_end,
        )

    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)

    for i in range(bar_count):
        pos = runtime.barcode_bars[i]
        x = int(pos * w) - (bar_w // 2)
        color_idx = i % len(palette)

        base = palette[color_idx]
        if prev_palette is not None:
            prev_c = prev_palette[color_idx]
            color = _blend(prev_c, base, blend_factor)
        else:
            color = QColor(base)

        alpha = _clamp(color.alpha() * 0.4, 0, 255)
        color.setAlpha(int(alpha))

        painter.setBrush(color)
        painter.drawRect(x, 0, bar_w, h)

    painter.restore()


def _paint_orbs(
    *,
    painter: QPainter,
    rect: QRect,
    runtime: _DynamicRuntime,
    spec: MidoriVariantSpec,
    blend_factor: float,
) -> None:
    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0 or runtime.orb_base_radius <= 0:
        return

    palette = spec.blob_palette
    orb_count = len(runtime.orb_positions)
    if orb_count == 0 or len(palette) == 0:
        return

    with _lock:
        prev_spec = _previous_spec

    prev_palette = None
    if prev_spec is not None and blend_factor < 1.0:
        prev_palette = prev_spec.blob_palette

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)

    if spec.light_mode:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    else:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)

    for i in range(orb_count):
        ox, oy = runtime.orb_positions[i]
        phase = runtime.orb_phases[i]
        cx = ox * w
        cy = oy * h

        size_osc = math.sin(runtime.tick_time * 1.5 + phase) * 0.3 + 1.0
        radius = runtime.orb_base_radius * size_osc

        alpha_osc = _clamp(math.sin(runtime.tick_time * 2.0 + phase + 1.0) * 0.25 + 0.7, 0.0, 1.0)

        color_idx = i % len(palette)
        base = palette[color_idx]

        if prev_palette is not None:
            prev_c = prev_palette[color_idx]
            color = _blend(prev_c, base, blend_factor)
        else:
            color = QColor(base)

        alpha = int(_clamp(color.alpha() * alpha_osc, 0, 255))
        color.setAlpha(alpha)

        gradient = QRadialGradient(QPointF(cx, cy), radius)
        gradient.setColorAt(0.0, color)
        gradient.setColorAt(
            0.5,
            QColor(color.red(), color.green(), color.blue(), int(alpha * 0.3)),
        )
        gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))

        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

    painter.restore()


def _paint_dynamic_blobs(
    *,
    painter: QPainter,
    rect: QRect,
    runtime: _DynamicRuntime,
    spec: MidoriVariantSpec,
    blend_factor: float,
) -> None:
    pulse = 0.5 + 0.5 * math.sin(runtime.pulse_phase)

    with _lock:
        prev_spec = _previous_spec

    if prev_spec is not None and blend_factor < 1.0:
        _midori_paint_blobs(
            painter=painter,
            rect=rect,
            runtime=runtime,  # pyright: ignore[reportArgumentType]
            pulse=pulse,
            spec=prev_spec,
        )
        painter.save()
        painter.setOpacity(blend_factor)

    _midori_paint_blobs(
        painter=painter,
        rect=rect,
        runtime=runtime,  # pyright: ignore[reportArgumentType]
        pulse=pulse,
        spec=spec,
    )

    if prev_spec is not None and blend_factor < 1.0:
        painter.restore()


class _DynamicBackground:
    theme_name = "dynamic"

    def base_color(self) -> QColor:
        with _lock:
            spec = _current_spec
        if spec is not None:
            return QColor(spec.base_color)
        return QColor(9, 8, 17)

    def overlay_alpha(self) -> int:
        return 30

    def init_runtime(self, *, widget: QWidget) -> object:
        runtime = _DynamicRuntime()
        runtime.rng.seed(time.time_ns())
        runtime.wave_phase = runtime.rng.uniform(0.0, math.tau)
        runtime.pulse_phase = runtime.rng.uniform(0.0, math.tau)
        runtime.width = int(widget.width())
        runtime.height = int(widget.height())
        runtime.orb_base_radius = float(min(runtime.width, runtime.height)) * 0.08
        runtime.blobs = _build_blob_seeds(runtime.rng, count=6)
        return runtime

    def on_resize(self, *, runtime: object, widget: QWidget) -> None:
        if not isinstance(runtime, _DynamicRuntime):
            return
        runtime.width = int(widget.width())
        runtime.height = int(widget.height())
        runtime.orb_base_radius = float(min(runtime.width, runtime.height)) * 0.08

    def tick(self, *, runtime: object, widget: QWidget, now_s: float, dt_s: float) -> bool:
        del widget
        del now_s
        if not isinstance(runtime, _DynamicRuntime):
            return True

        step = float(dt_s) * 0.85
        runtime.tick_time += step
        runtime.wave_phase = (runtime.wave_phase + (step * 0.95)) % math.tau
        runtime.pulse_phase = (runtime.pulse_phase + (step * 1.22)) % math.tau

        base_split = 0.46 + (0.11 * math.sin((runtime.tick_time * 0.52) + 0.8))
        detail = 0.015 * math.sin((runtime.tick_time * 2.3) + (runtime.wave_phase * 0.35))
        runtime.split_ratio = _clamp(base_split + detail, 0.30, 0.62)

        runtime.top_phase = 0.5 + (0.5 * math.sin((runtime.tick_time * 0.41) + 1.2))
        runtime.bottom_phase = 0.5 + (0.5 * math.cos((runtime.tick_time * 0.36) + 2.0))

        for i in range(len(runtime.barcode_bars)):
            runtime.barcode_bars[i] += runtime.barcode_directions[i] * step
            if runtime.barcode_bars[i] > 1.1:
                runtime.barcode_bars[i] -= 1.1
            elif runtime.barcode_bars[i] < -0.1:
                runtime.barcode_bars[i] += 1.1

        return True

    def paint(self, *, painter: QPainter, rect: QRect, runtime: object) -> None:
        if not isinstance(runtime, _DynamicRuntime):
            return

        with _lock:
            current = _current_spec
            previous = _previous_spec
            style = _current_style
            t_start = _transition_start_s

        if t_start is not None and previous is not None:
            blend_factor = _clamp((time.monotonic() - t_start) / _transition_duration, 0.0, 1.0)
        else:
            blend_factor = 1.0

        resolved = current if current is not None else _FALLBACK_SPEC
        resolved_style = style if current is not None else "blobs"

        if previous is not None and blend_factor < 1.0:
            self._paint_style(
                painter=painter,
                rect=rect,
                runtime=runtime,
                spec=previous,
                style=resolved_style,
                blend_factor=1.0,
            )
            painter.save()
            painter.setOpacity(blend_factor)

        self._paint_style(
            painter=painter,
            rect=rect,
            runtime=runtime,
            spec=resolved,
            style=resolved_style,
            blend_factor=blend_factor,
        )

        if previous is not None and blend_factor < 1.0:
            painter.restore()

    @staticmethod
    def _paint_style(
        *,
        painter: QPainter,
        rect: QRect,
        runtime: _DynamicRuntime,
        spec: MidoriVariantSpec,
        style: str,
        blend_factor: float,
    ) -> None:
        pulse = 0.5 + 0.5 * math.sin(runtime.pulse_phase)
        top_color = _blend(spec.top_start, spec.top_end, runtime.top_phase)
        bottom_color = _blend(spec.bottom_start, spec.bottom_end, runtime.bottom_phase)

        _apply_base_gradient(
            painter=painter,
            rect=rect,
            top_color=top_color,
            bottom_color=bottom_color,
            pulse=pulse,
            wave_phase=runtime.wave_phase,
            split_ratio=runtime.split_ratio,
            spec=spec,
        )

        if style == "barcode":
            _paint_barcode(
                painter=painter,
                rect=rect,
                runtime=runtime,
                spec=spec,
                blend_factor=blend_factor,
            )
        elif style == "orbs":
            _paint_orbs(
                painter=painter,
                rect=rect,
                runtime=runtime,
                spec=spec,
                blend_factor=blend_factor,
            )
        else:
            _paint_dynamic_blobs(
                painter=painter,
                rect=rect,
                runtime=runtime,
                spec=spec,
                blend_factor=blend_factor,
            )

        if spec.ambient_overlay.alpha() > 0:
            painter.fillRect(rect, spec.ambient_overlay)


BACKGROUND = _DynamicBackground()
