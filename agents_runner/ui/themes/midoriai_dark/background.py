"""Midori AI Dark theme background implementation."""

from __future__ import annotations

from PySide6.QtGui import QColor

from agents_runner.ui.themes.midori_variant import MidoriVariantSpec
from agents_runner.ui.themes.midori_variant import create_midori_background


_SPEC = MidoriVariantSpec(
    theme_name="midoriai_dark",
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

BACKGROUND = create_midori_background(_SPEC)
