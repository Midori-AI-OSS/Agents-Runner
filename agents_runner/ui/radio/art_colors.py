"""Functions to download album art, extract dominant colors, and build dynamic theme specs."""

from __future__ import annotations

import hashlib
from typing import Callable

from PySide6.QtCore import QUrl
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtNetwork import QNetworkRequest

from agents_runner.ui.themes.midoriai_variant import MidoriaiVariantSpec


def download_art(
    art_url: str,
    network: QNetworkAccessManager,
    callback: Callable[[QImage | None], None],
) -> QNetworkReply:
    """Download album art and return the reply so callers can cancel stale requests."""
    request = QNetworkRequest(QUrl(art_url))
    reply = network.get(request)

    def _on_finished() -> None:
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            image = QImage.fromData(data)
            callback(image)
        else:
            callback(None)
        reply.deleteLater()

    reply.finished.connect(_on_finished)
    return reply


def extract_dominant_colors(image: QImage, n: int = 4) -> list[QColor]:
    """Extract the *n* most frequent colors from *image*."""
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        return [QColor(9, 8, 17)] * n

    scaled = image.scaled(
        64,
        64,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    freq: dict[tuple[int, int, int], int] = {}
    for y in range(scaled.height()):
        for x in range(scaled.width()):
            color = scaled.pixelColor(x, y)
            key = (color.red(), color.green(), color.blue())
            freq[key] = freq.get(key, 0) + 1

    sorted_keys = sorted(freq, key=lambda k: freq[k], reverse=True)
    colors: list[QColor] = [QColor(*k) for k in sorted_keys[:n]]

    while len(colors) < n:
        colors.append(QColor(9, 8, 17))

    return colors


def hash_to_style(track_title: str) -> str:
    """Deterministically map *track_title* to a visual style."""
    if not track_title:
        return "blobs"
    digest = hashlib.sha256(track_title.encode("utf-8")).digest()
    mapping = {0: "barcode", 1: "orbs", 2: "blobs"}
    return mapping[digest[0] % 3]


def build_dynamic_spec(colors: list[QColor], style: str) -> MidoriaiVariantSpec:
    """Build a MidoriaiVariantSpec from extracted *colors* and *style* string."""
    del style  # style is reserved for future use
    safe_colors = (colors or [])[:4]
    while len(safe_colors) < 4:
        safe_colors.append(QColor(9, 8, 17))

    def _luminance(c: QColor) -> float:
        return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()

    sorted_colors = sorted(safe_colors, key=_luminance)

    base_color = sorted_colors[0]
    top_start = sorted_colors[2]
    top_end = sorted_colors[3]
    bottom_start = sorted_colors[1]
    bottom_end = sorted_colors[0]

    blob_list: list[QColor] = []
    for i in range(4):
        c = sorted_colors[i]
        blob_list.append(QColor(c.red(), c.green(), c.blue(), 208))

    c2 = sorted_colors[1]
    c3 = sorted_colors[2]
    blended = QColor(
        int((c2.red() + c3.red()) / 2),
        int((c2.green() + c3.green()) / 2),
        int((c2.blue() + c3.blue()) / 2),
        182,
    )
    blob_list.append(blended)

    darkest = sorted_colors[0]
    lighter = QColor(
        int(darkest.red() * 0.5 + 255 * 0.5),
        int(darkest.green() * 0.5 + 255 * 0.5),
        int(darkest.blue() * 0.5 + 255 * 0.5),
        165,
    )
    blob_list.append(lighter)

    avg_lum = sum(_luminance(c) for c in sorted_colors) / 4
    light_mode = avg_lum > 128.0

    return MidoriaiVariantSpec(
        theme_name="dynamic",
        base_color=base_color,
        overlay_alpha=30,
        top_start=top_start,
        top_end=top_end,
        bottom_start=bottom_start,
        bottom_end=bottom_end,
        blob_palette=tuple(blob_list),
        ambient_overlay=QColor(0, 0, 0, 50),
        boundary_angle_deg=17.0,
        motion_speed=1.22,
        wave_strength=0.42,
        pulse_strength=0.44,
        light_mode=light_mode,
    )
