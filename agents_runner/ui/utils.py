from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox

from agents_runner.log_format import parse_docker_datetime


def parse_docker_time(value: str | None) -> datetime | None:
    dt = parse_docker_datetime(value)
    # Docker reports Go's "zero time" for fields like FinishedAt while running.
    # Treat anything pre-epoch as unset.
    return dt if dt and dt.year >= 1970 else None


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, rem = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {int(rem)}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def safe_str(value: object, default: str = "") -> str:
    """Convert value to stripped string, returning default if empty."""
    return str(value or default).strip() or default


def looks_like_agent_help_command(command: str) -> bool:
    value = str(command or "").strip()
    if not value:
        return False
    lowered = value.lower()
    return "agent-help" in lowered or ".agent-help" in lowered


def status_color(status: str) -> QColor:
    """Map status string to color."""
    color_map = {
        "pulling": (56, 189, 248, 220),
        "cleaning": (56, 189, 248, 220),
        "done": (16, 185, 129, 230),
        "failed": (244, 63, 94, 230),
        "cancelled": (245, 158, 11, 230),
        "killed": (244, 63, 94, 230),
        "created": (148, 163, 184, 220),
        "running": (16, 185, 129, 220),
        "paused": (245, 158, 11, 220),
        "restarting": (56, 189, 248, 220),
        "removing": (56, 189, 248, 220),
        "exited": (148, 163, 184, 220),
        "dead": (148, 163, 184, 220),
        "error": (244, 63, 94, 220),
    }
    rgba = color_map.get((status or "").lower(), (148, 163, 184, 220))
    return QColor(*rgba)


def rgba(color: QColor, alpha: int | None = None) -> str:
    """Convert QColor to CSS rgba() string."""
    a = color.alpha() if alpha is None else alpha
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(a)})"


def stain_color(stain: str) -> QColor:
    """Map stain name to color."""
    color_map = {
        "cyan": (56, 189, 248, 220),
        "emerald": (16, 185, 129, 220),
        "violet": (139, 92, 246, 220),
        "rose": (244, 63, 94, 220),
        "amber": (245, 158, 11, 220),
        "blue": (59, 130, 246, 220),
        "teal": (20, 184, 166, 220),
        "lime": (132, 204, 22, 220),
        "fuchsia": (217, 70, 239, 220),
        "indigo": (99, 102, 241, 220),
        "orange": (249, 115, 22, 220),
    }
    rgba = color_map.get((stain or "").strip().lower(), (148, 163, 184, 220))
    return QColor(*rgba)


def blend_rgb(a: QColor, b: QColor, t: float) -> QColor:
    t = float(min(max(t, 0.0), 1.0))
    r = int(round(a.red() + (b.red() - a.red()) * t))
    g = int(round(a.green() + (b.green() - a.green()) * t))
    bb = int(round(a.blue() + (b.blue() - a.blue()) * t))
    return QColor(r, g, bb)


def apply_environment_combo_tint(combo: QComboBox, stain: str) -> None:
    env = stain_color(stain)
    base = QColor(18, 20, 28)
    tinted = blend_rgb(base, QColor(env.red(), env.green(), env.blue()), 0.40)
    combo.setStyleSheet(
        "\n".join(
            [
                "QComboBox {",
                f"  background-color: {rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 190))};",
                "}",
                "QComboBox::drop-down {",
                f"  background-color: {rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 135))};",
                "}",
                "QComboBox QAbstractItemView {",
                f"  background-color: {rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 240))};",
                f"  selection-background-color: {rgba(QColor(env.red(), env.green(), env.blue(), 95))};",
                "}",
            ]
        )
    )
