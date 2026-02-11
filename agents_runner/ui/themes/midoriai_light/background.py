"""Midori AI Light theme background implementation."""

from __future__ import annotations

from PySide6.QtGui import QColor

from agents_runner.ui.themes.midori_variant import MidoriVariantSpec
from agents_runner.ui.themes.midori_variant import create_midori_background


_SPEC = MidoriVariantSpec(
    theme_name="midoriai_light",
    base_color=QColor(236, 233, 246),
    overlay_alpha=8,
    top_start=QColor("#E9EDFF"),
    top_end=QColor("#E8DCFF"),
    bottom_start=QColor("#FFECDD"),
    bottom_end=QColor("#F5DCF7"),
    blob_palette=(
        QColor(121, 122, 228, 120),
        QColor(173, 112, 230, 112),
        QColor(250, 169, 104, 108),
        QColor(242, 131, 156, 102),
        QColor(112, 180, 232, 104),
        QColor(207, 132, 223, 100),
    ),
    ambient_overlay=QColor(255, 255, 255, 20),
    boundary_angle_deg=14.0,
    motion_speed=1.14,
    wave_strength=0.30,
    pulse_strength=0.32,
    light_mode=True,
)

BACKGROUND = create_midori_background(_SPEC)
