from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


@runtime_checkable
class ThemeBackground(Protocol):
    """Theme background contract used by `agents_runner.ui.graphics`.

    Theme modules (`agents_runner/ui/themes/<name>/background.py`) should export a
    `BACKGROUND` object implementing this protocol. Theme-specific state is
    stored in the theme's runtime object returned by `init_runtime`.
    """

    theme_name: str

    def base_color(self) -> QColor: ...

    def overlay_alpha(self) -> int: ...

    def init_runtime(self, *, widget: QWidget) -> object: ...

    def on_resize(self, *, runtime: object, widget: QWidget) -> None: ...

    def tick(
        self, *, runtime: object, widget: QWidget, now_s: float, dt_s: float
    ) -> bool: ...

    def paint(self, *, painter: QPainter, rect: QRect, runtime: object) -> None: ...
