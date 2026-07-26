"""OpenCode theme background implementation."""

from __future__ import annotations

from PySide6.QtGui import QColor

from agents_runner.ui.themes.midoriai_variant import MidoriaiVariantSpec
from agents_runner.ui.themes.midoriai_variant import create_midoriai_background


_SPEC = MidoriaiVariantSpec(
    theme_name="opencode",
    base_color=QColor(14, 19, 23),
    overlay_alpha=18,
    top_start=QColor("#203347"),
    top_end=QColor("#1B6D67"),
    bottom_start=QColor("#171F28"),
    bottom_end=QColor("#D36B2E"),
    blob_palette=(
        QColor(102, 205, 197, 182),
        QColor(80, 156, 208, 168),
        QColor(248, 176, 80, 176),
        QColor(224, 112, 64, 170),
        QColor(165, 226, 180, 146),
        QColor(245, 206, 126, 132),
    ),
    ambient_overlay=QColor(0, 0, 0, 24),
    boundary_angle_deg=16.0,
    motion_speed=1.02,
    wave_strength=0.24,
    pulse_strength=0.24,
    light_mode=False,
)

BACKGROUND = create_midoriai_background(_SPEC)
