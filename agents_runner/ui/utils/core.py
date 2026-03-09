from __future__ import annotations

import hashlib

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ChatBubbleTone:
    fill: QColor
    border: QColor
    text_primary: QColor
    text_secondary: QColor
    action_fill: QColor
    action_border: QColor
    action_hover_fill: QColor
    action_hover_border: QColor


def _hue_distance(a: int, b: int) -> int:
    if a < 0 or b < 0:
        return 180
    distance = abs(int(a) - int(b)) % 360
    return min(distance, 360 - distance)


def _relative_luminance(color: QColor) -> float:
    def _linear(channel: int) -> float:
        value = float(max(0, min(255, int(channel)))) / 255.0
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    r = _linear(color.red())
    g = _linear(color.green())
    b = _linear(color.blue())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(a: QColor, b: QColor) -> float:
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    lighter = max(la, lb)
    darker = min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _normalize_username(username: str) -> str:
    value = str(username or "").strip().lower().lstrip("@")
    return value or "unknown"


def _hash_hsl_color(seed: str) -> QColor:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    raw_hue = int.from_bytes(digest[0:2], byteorder="big", signed=False) % 360
    # Quantize hue in coarse buckets to reduce near-identical colors.
    hue_step = 24
    hue = int(round(raw_hue / hue_step) * hue_step) % 360
    saturation = 160 + int(digest[2] % 72)  # 160-231
    lightness = 96 + int(digest[3] % 56)  # 96-151
    return QColor.fromHsl(hue, saturation, lightness, 255)


def _candidate_far_from_environment(candidate: QColor, env: QColor) -> bool:
    if _hue_distance(candidate.hslHue(), env.hslHue()) < 34:
        return False
    if abs(_relative_luminance(candidate) - _relative_luminance(env)) < 0.12:
        return False
    return True


def _ensure_contrast(fill: QColor, text: QColor, *, min_ratio: float) -> QColor:
    candidate = QColor(fill.red(), fill.green(), fill.blue(), fill.alpha())
    for _ in range(10):
        if _contrast_ratio(candidate, text) >= min_ratio:
            return candidate
        darkened = blend_rgb(candidate, QColor(0, 0, 0), 0.16)
        candidate = QColor(
            darkened.red(), darkened.green(), darkened.blue(), fill.alpha()
        )
    return candidate


def username_bubble_color(
    username: str,
    *,
    env_stain: str,
    strict: bool = True,
) -> QColor:
    normalized = _normalize_username(username)
    env = stain_color(env_stain)
    max_attempts = 24
    for attempt in range(1, max_attempts + 1):
        # Salting with "a" is color-system-only and keeps output deterministic.
        salted = f"{normalized}{'a' * attempt}"
        candidate = _hash_hsl_color(salted)
        if not strict or _candidate_far_from_environment(candidate, env):
            return candidate

    fallback = _hash_hsl_color(f"{normalized}{'a' * max_attempts}")
    hue = fallback.hslHue()
    if hue < 0:
        hue = 210
    rotated = QColor.fromHsl(
        (hue + 120) % 360, fallback.hslSaturation(), fallback.lightness()
    )
    return rotated


def resolve_chat_bubble_tone(
    *,
    role: str,
    env_stain: str,
    username: str,
) -> ChatBubbleTone:
    normalized_role = str(role or "").strip().lower()
    base = (
        stain_color(env_stain)
        if normalized_role == "self"
        else username_bubble_color(username, env_stain=env_stain, strict=True)
    )
    canvas = QColor(18, 20, 28)
    text_primary = QColor(237, 239, 245, 235)
    text_secondary = QColor(237, 239, 245, 170)

    fill_base = blend_rgb(canvas, base, 0.40)
    fill = QColor(fill_base.red(), fill_base.green(), fill_base.blue(), 222)
    fill = _ensure_contrast(fill, text_primary, min_ratio=4.8)

    border_base = blend_rgb(canvas, base, 0.66)
    border = QColor(border_base.red(), border_base.green(), border_base.blue(), 220)

    action_fill_base = blend_rgb(canvas, base, 0.52)
    action_fill = QColor(
        action_fill_base.red(),
        action_fill_base.green(),
        action_fill_base.blue(),
        164,
    )

    action_border_base = blend_rgb(canvas, base, 0.76)
    action_border = QColor(
        action_border_base.red(),
        action_border_base.green(),
        action_border_base.blue(),
        228,
    )

    action_hover_fill_base = blend_rgb(action_fill, QColor(255, 255, 255), 0.18)
    action_hover_fill = QColor(
        action_hover_fill_base.red(),
        action_hover_fill_base.green(),
        action_hover_fill_base.blue(),
        188,
    )

    action_hover_border_base = blend_rgb(action_border, QColor(255, 255, 255), 0.22)
    action_hover_border = QColor(
        action_hover_border_base.red(),
        action_hover_border_base.green(),
        action_hover_border_base.blue(),
        236,
    )

    return ChatBubbleTone(
        fill=fill,
        border=border,
        text_primary=text_primary,
        text_secondary=text_secondary,
        action_fill=action_fill,
        action_border=action_border,
        action_hover_fill=action_hover_fill,
        action_hover_border=action_hover_border,
    )
