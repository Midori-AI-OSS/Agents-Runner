from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtGui import QIcon

from agents_runner.ui.lucide_icons import lucide_icon


def _app_icon() -> QIcon | None:
    icon_path = Path(__file__).resolve().parent.parent / "midoriai-logo.png"
    return QIcon(str(icon_path)) if icon_path.exists() else None


def mic_icon(*, size: int = 18, color: QColor | None = None) -> QIcon:
    return lucide_icon("audio-lines", size=size, color=color)
