from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QIcon
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPixmap


def _app_icon() -> QIcon | None:
    icon_path = Path(__file__).resolve().parent.parent / "midoriai-logo.png"
    return QIcon(str(icon_path)) if icon_path.exists() else None


def mic_icon(*, size: int = 18, color: QColor | None = None) -> QIcon:
    color = color or QColor(237, 239, 245)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(color)

    body_w = max(6, int(size * 0.36))
    body_h = max(10, int(size * 0.52))
    body_x = int((size - body_w) / 2)
    body_y = max(1, int(size * 0.12))
    p.drawRect(body_x, body_y, body_w, body_h)

    stem_w = max(3, int(size * 0.14))
    stem_h = max(3, int(size * 0.16))
    stem_x = int((size - stem_w) / 2)
    stem_y = body_y + body_h
    p.drawRect(stem_x, stem_y, stem_w, stem_h)

    base_w = max(8, int(size * 0.46))
    base_h = max(2, int(size * 0.10))
    base_x = int((size - base_w) / 2)
    base_y = min(size - base_h - 1, stem_y + stem_h)
    p.drawRect(base_x, base_y, base_w, base_h)

    p.end()
    return QIcon(pm)
