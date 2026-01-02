from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def _app_icon() -> QIcon | None:
    icon_path = Path(__file__).resolve().parent.parent / "midoriai-logo.png"
    return QIcon(str(icon_path)) if icon_path.exists() else None
