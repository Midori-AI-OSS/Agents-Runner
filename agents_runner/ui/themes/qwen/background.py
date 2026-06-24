"""Qwen theme background implementation."""

from __future__ import annotations

from PySide6.QtGui import QColor

from agents_runner.ui.themes.midoriai_variant import MidoriaiVariantSpec
from agents_runner.ui.themes.midoriai_variant import create_midoriai_background


_SPEC = MidoriaiVariantSpec(
    theme_name="qwen",
    base_color=QColor(12, 18, 24),
    overlay_alpha=20,
    top_start=QColor("#15324F"),
    top_end=QColor("#0C7A83"),
    bottom_start=QColor("#14212A"),
    bottom_end=QColor("#C7742B"),
    blob_palette=(
        QColor(82, 192, 216, 190),
        QColor(52, 165, 151, 176),
        QColor(246, 168, 84, 170),
        QColor(241, 125, 73, 160),
        QColor(131, 197, 255, 150),
        QColor(167, 230, 218, 138),
    ),
    ambient_overlay=QColor(0, 0, 0, 26),
    boundary_angle_deg=15.0,
    motion_speed=1.08,
    wave_strength=0.26,
    pulse_strength=0.28,
    light_mode=False,
)

BACKGROUND = create_midoriai_background(_SPEC)
