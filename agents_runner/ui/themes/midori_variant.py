"""Shared Midori AI background renderer for dark/light variants."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from dataclasses import field

from PySide6.QtCore import QPointF
from PySide6.QtCore import QRect
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QLinearGradient
from PySide6.QtGui import QPainter
from PySide6.QtGui import QRadialGradient
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class MidoriVariantSpec:
    """Visual and motion parameters for a Midori theme variant."""

    theme_name: str
    base_color: QColor
    overlay_alpha: int
    top_start: QColor
    top_end: QColor
    bottom_start: QColor
    bottom_end: QColor
    blob_palette: tuple[QColor, ...]
    ambient_overlay: QColor
    boundary_angle_deg: float = 16.0
    motion_speed: float = 1.0
    wave_strength: float = 0.3
    pulse_strength: float = 0.3
    light_mode: bool = False


@dataclass(frozen=True)
class _BlobSeed:
    nx: float
    ny: float
    rx_scale: float
    ry_scale: float
    jitter_x: float
    jitter_y: float
    phase: float
    speed: float
    color_index: int


@dataclass
class _MidoriRuntime:
    split_ratio: float = 0.45
    top_phase: float = 0.0
    bottom_phase: float = 0.0
    wave_phase: float = 0.0
    pulse_phase: float = 0.0
    tick_time: float = 0.0
    rng: random.Random = field(default_factory=random.Random)
    blobs: tuple[_BlobSeed, ...] = tuple()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _blend(color1: QColor | str, color2: QColor | str, t: float) -> QColor:
    c1 = QColor(color1) if isinstance(color1, str) else color1
    c2 = QColor(color2) if isinstance(color2, str) else color2
    t = _clamp(float(t), 0.0, 1.0)
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


def _build_blob_seeds(rng: random.Random, *, count: int) -> tuple[_BlobSeed, ...]:
    seeds: list[_BlobSeed] = []
    for _ in range(max(1, count)):
        seeds.append(
            _BlobSeed(
                nx=rng.uniform(0.10, 0.90),
                ny=rng.uniform(0.15, 0.85),
                rx_scale=rng.uniform(0.58, 0.96),
                ry_scale=rng.uniform(0.46, 0.78),
                jitter_x=rng.uniform(0.015, 0.045),
                jitter_y=rng.uniform(0.010, 0.038),
                phase=rng.uniform(0.0, math.tau),
                speed=rng.uniform(0.14, 0.33),
                color_index=rng.randint(0, 1024),
            )
        )
    return tuple(seeds)


def _apply_base_gradient(
    *,
    painter: QPainter,
    rect: QRect,
    top_color: QColor,
    bottom_color: QColor,
    pulse: float,
    wave_phase: float,
    split_ratio: float,
    spec: MidoriVariantSpec,
) -> None:
    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0:
        return

    theta = math.radians(float(spec.boundary_angle_deg))
    m = math.tan(theta)
    n_len = math.hypot(m, 1.0)
    n_x = -m / n_len
    n_y = 1.0 / n_len

    wave = math.sin(wave_phase)
    wave_shift_x = 0.09 * spec.wave_strength * wave
    wave_shift_y = 0.022 * spec.wave_strength * math.sin((wave_phase * 1.7) + 0.7)

    mid_x = float(w) * (0.5 + wave_shift_x)
    mid_y = float(h) * (split_ratio + wave_shift_y)

    extent = float(max(w, h)) * 1.2
    start = QPointF(mid_x - (n_x * extent), mid_y - (n_y * extent))
    end = QPointF(mid_x + (n_x * extent), mid_y + (n_y * extent))

    if spec.light_mode:
        c0 = _blend(top_color, QColor(255, 255, 255), 0.40 + (0.08 * pulse))
        c1 = _blend(top_color, bottom_color, 0.34)
        c2 = _blend(top_color, bottom_color, 0.66)
        c3 = _blend(bottom_color, QColor(255, 250, 240), 0.30 + (0.05 * (1.0 - pulse)))
    else:
        c0 = _blend(top_color, QColor(236, 228, 255), 0.16 + (0.08 * pulse))
        c1 = _blend(top_color, bottom_color, 0.36)
        c2 = _blend(top_color, bottom_color, 0.68)
        c3 = _blend(bottom_color, QColor(255, 204, 144), 0.12 + (0.10 * pulse))

    gradient = QLinearGradient(start, end)
    gradient.setColorAt(0.0, c0)
    gradient.setColorAt(0.42, c1)
    gradient.setColorAt(0.64, c2)
    gradient.setColorAt(1.0, c3)
    painter.fillRect(0, 0, w, h, gradient)


def _paint_blobs(
    *,
    painter: QPainter,
    rect: QRect,
    runtime: _MidoriRuntime,
    pulse: float,
    spec: MidoriVariantSpec,
) -> None:
    w = int(rect.width())
    h = int(rect.height())
    if w <= 0 or h <= 0 or not runtime.blobs or not spec.blob_palette:
        return

    size = float(min(w, h))
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)

    if spec.light_mode:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    else:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)

    pulse_scale = 1.0 + ((pulse - 0.5) * spec.pulse_strength * 0.25)

    for seed in runtime.blobs:
        drift = runtime.tick_time
        wave_x = math.sin(runtime.wave_phase + seed.phase + (seed.ny * math.pi * 2.0))
        wave_y = math.cos(
            (runtime.wave_phase * 0.7) + (seed.phase * 0.65) + (seed.nx * math.pi)
        )
        drift_x = math.sin((drift * seed.speed) + seed.phase)
        drift_y = math.cos((drift * (seed.speed * 0.83)) + (seed.phase * 1.15))

        cx = float(w) * (
            seed.nx + (seed.jitter_x * drift_x) + (0.055 * spec.wave_strength * wave_x)
        )
        cy = float(h) * (
            seed.ny + (seed.jitter_y * drift_y) + (0.018 * spec.wave_strength * wave_y)
        )

        rx = max(1.0, size * seed.rx_scale * pulse_scale)
        ry = max(1.0, size * seed.ry_scale * pulse_scale)

        base_color = spec.blob_palette[seed.color_index % len(spec.blob_palette)]
        alpha_gain = 0.75 + (0.35 * pulse)
        alpha = int(_clamp(base_color.alpha() * alpha_gain, 0.0, 255.0))
        color = QColor(base_color.red(), base_color.green(), base_color.blue(), alpha)

        painter.save()
        painter.translate(QPointF(cx, cy))
        painter.scale(rx, ry)

        gradient = QRadialGradient(QPointF(0.0, 0.0), 1.0)
        gradient.setColorAt(0.0, color)
        gradient.setColorAt(
            0.48,
            QColor(
                color.red(),
                color.green(),
                color.blue(),
                int(color.alpha() * 0.25),
            ),
        )
        gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))

        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(0.0, 0.0), 1.0, 1.0)
        painter.restore()

    painter.restore()


def _paint_variant(
    *,
    painter: QPainter,
    rect: QRect,
    runtime: _MidoriRuntime,
    spec: MidoriVariantSpec,
) -> None:
    top_color = _blend(spec.top_start, spec.top_end, runtime.top_phase)
    bottom_color = _blend(spec.bottom_start, spec.bottom_end, runtime.bottom_phase)

    pulse = 0.5 + (0.5 * math.sin(runtime.pulse_phase))

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
    _paint_blobs(
        painter=painter,
        rect=rect,
        runtime=runtime,
        pulse=pulse,
        spec=spec,
    )

    if spec.ambient_overlay.alpha() > 0:
        painter.fillRect(rect, spec.ambient_overlay)


class _MidoriVariantBackground:
    def __init__(self, spec: MidoriVariantSpec) -> None:
        self._spec = spec
        self.theme_name = spec.theme_name

    def base_color(self) -> QColor:
        return QColor(self._spec.base_color)

    def overlay_alpha(self) -> int:
        return int(_clamp(float(self._spec.overlay_alpha), 0.0, 255.0))

    def init_runtime(self, *, widget: QWidget) -> object:
        del widget
        runtime = _MidoriRuntime()
        runtime.rng.seed(time.time_ns())
        runtime.wave_phase = runtime.rng.uniform(0.0, math.tau)
        runtime.pulse_phase = runtime.rng.uniform(0.0, math.tau)
        runtime.blobs = _build_blob_seeds(runtime.rng, count=6)
        return runtime

    def on_resize(self, *, runtime: object, widget: QWidget) -> None:
        del runtime
        del widget
        return

    def tick(
        self, *, runtime: object, widget: QWidget, now_s: float, dt_s: float
    ) -> bool:
        del widget
        del now_s
        state = runtime if isinstance(runtime, _MidoriRuntime) else _MidoriRuntime()

        speed = max(0.2, float(self._spec.motion_speed))
        step = float(dt_s) * speed
        state.tick_time += step

        state.wave_phase = (state.wave_phase + (step * 0.95)) % math.tau
        state.pulse_phase = (state.pulse_phase + (step * 1.22)) % math.tau

        base_split = 0.46 + (0.11 * math.sin((state.tick_time * 0.52) + 0.8))
        detail = 0.015 * math.sin((state.tick_time * 2.3) + (state.wave_phase * 0.35))
        state.split_ratio = _clamp(base_split + detail, 0.30, 0.62)

        state.top_phase = 0.5 + (0.5 * math.sin((state.tick_time * 0.41) + 1.2))
        state.bottom_phase = 0.5 + (0.5 * math.cos((state.tick_time * 0.36) + 2.0))
        return True

    def paint(self, *, painter: QPainter, rect: QRect, runtime: object) -> None:
        state = runtime if isinstance(runtime, _MidoriRuntime) else _MidoriRuntime()
        _paint_variant(painter=painter, rect=rect, runtime=state, spec=self._spec)


def create_midori_background(spec: MidoriVariantSpec) -> object:
    """Create a background implementation for a Midori variant."""

    return _MidoriVariantBackground(spec)
