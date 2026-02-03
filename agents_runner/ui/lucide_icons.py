from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from agents_runner.ui.style.palette import TEXT_PRIMARY


def lucide_icon(
    name: str,
    *,
    size: int = 16,
    color: QColor | None = None,
) -> QIcon:
    """Load and render a Lucide icon with HiDPI support.

    Args:
        name: Icon name (e.g., "house", "folder", "trash-2")
        size: Base icon size in logical pixels
        color: Icon color (defaults to app primary text color)

    Returns:
        QIcon with properly scaled HiDPI pixmap

    Example:
        >>> icon = lucide_icon("house", size=24, color=QColor(255, 255, 255))
    """
    # Get device pixel ratio for HiDPI rendering
    # Use a pixmap to get the device pixel ratio from the current screen
    temp_pixmap = QPixmap(1, 1)
    dpr = temp_pixmap.devicePixelRatio()

    if color is None:
        color = QColor(TEXT_PRIMARY)

    # Convert color to RGBA tuple for cache key
    color_key = color.getRgb()

    # Get cached or render new pixmap
    pixmap = _render_lucide_icon(name, size, color_key, dpr)

    return QIcon(pixmap)


@lru_cache(maxsize=128)
def _render_lucide_icon(
    name: str,
    size: int,
    color_key: tuple[int, int, int, int] | None,
    dpr: float,
) -> QPixmap:
    """Internal: Render and cache a Lucide icon pixmap.

    Args:
        name: Icon name
        size: Base icon size in logical pixels
        color_key: RGBA tuple for color or None
        dpr: Device pixel ratio

    Returns:
        HiDPI-aware QPixmap
    """
    # Load SVG file
    icon_path = (
        Path(__file__).parent.parent / "assets" / "icons" / "lucide" / f"{name}.svg"
    )

    if not icon_path.exists():
        # Return empty pixmap if icon not found
        pixmap = QPixmap(int(size * dpr), int(size * dpr))
        pixmap.fill(Qt.transparent)
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    # Read SVG content
    svg_data = icon_path.read_bytes()

    # Replace currentColor with desired color
    if color_key is not None:
        # Reconstruct QColor from RGBA tuple
        color = QColor(*color_key)
        hex_color = color.name()  # Returns #RRGGBB format
        svg_data = svg_data.replace(b"currentColor", hex_color.encode("ascii"))

    # Create renderer from modified SVG
    renderer = QSvgRenderer(QByteArray(svg_data))

    if not renderer.isValid():
        # Return empty pixmap if SVG is invalid
        pixmap = QPixmap(int(size * dpr), int(size * dpr))
        pixmap.fill(Qt.transparent)
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    # Create HiDPI pixmap
    physical_size = int(size * dpr)
    pixmap = QPixmap(physical_size, physical_size)
    pixmap.fill(Qt.transparent)
    pixmap.setDevicePixelRatio(dpr)

    # Render SVG into pixmap
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap
