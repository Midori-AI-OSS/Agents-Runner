from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPaintEvent, QPainter
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from agents_runner.ui.graphics import _load_background
from agents_runner.ui.graphics import _resolve_theme_name
from agents_runner.ui.themes.types import ThemeBackground


class ThemePreviewWidget(QWidget):
    """Live background preview surface for a single UI theme."""

    def __init__(self, theme_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme_name = ""
        self._background: ThemeBackground | None = None
        self._runtime: object | None = None
        self._tick_last_s = time.monotonic()

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._ticker = QTimer(self)
        self._ticker.setInterval(100)
        self._ticker.timeout.connect(self._update_animation)
        self._ticker.start()

        self.set_theme_name(theme_name)

    def theme_name(self) -> str:
        return self._theme_name

    def set_theme_name(self, theme_name: str) -> None:
        resolved = _resolve_theme_name(theme_name)
        if resolved == self._theme_name and self._background is not None:
            return

        self._theme_name = resolved
        self._background = _load_background(resolved)
        self._runtime = None

        if self._background is not None:
            try:
                self._runtime = self._background.init_runtime(widget=self)
            except Exception:
                self._runtime = None

        self._tick_last_s = time.monotonic()
        self._notify_resize()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._notify_resize()

    def _notify_resize(self) -> None:
        if self._background is None or self._runtime is None:
            return
        try:
            self._background.on_resize(runtime=self._runtime, widget=self)
        except Exception:
            return

    def _update_animation(self) -> None:
        now_s = time.monotonic()
        dt_s = float(now_s - float(self._tick_last_s))
        if dt_s <= 0.0:
            return

        self._tick_last_s = now_s
        dt_s = float(min(dt_s, 0.25))

        if self._background is None or self._runtime is None:
            return

        repaint = False
        try:
            repaint = bool(
                self._background.tick(
                    runtime=self._runtime,
                    widget=self,
                    now_s=now_s,
                    dt_s=dt_s,
                )
            )
        except Exception:
            repaint = True

        if repaint:
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        if rect.isEmpty():
            return

        if self._background is None or self._runtime is None:
            painter.fillRect(rect, QColor(10, 11, 13))
            return

        try:
            self._background.paint(painter=painter, rect=rect, runtime=self._runtime)
        except Exception:
            painter.fillRect(rect, self._background.base_color())

        alpha = 32
        try:
            alpha = int(self._background.overlay_alpha())
        except Exception:
            alpha = 32

        alpha = min(max(alpha, 0), 255)
        painter.fillRect(rect, QColor(0, 0, 0, alpha))


class ThemePreviewTile(QFrame):
    """Clickable tile showing a live theme preview and label."""

    clicked = Signal(str)

    def __init__(
        self,
        *,
        theme_name: str,
        label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_name = str(theme_name or "").strip().lower()

        self.setObjectName("ThemePreviewTile")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(170, 130)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._preview = ThemePreviewWidget(self._theme_name, self)
        self._preview.setObjectName("ThemePreviewCanvas")
        self._preview.setMinimumHeight(92)
        self._preview.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._preview, 1)

        self._label = QLabel(label, self)
        self._label.setObjectName("ThemePreviewTileLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._label)

    def theme_name(self) -> str:
        return self._theme_name

    def set_selected(self, selected: bool) -> None:
        target = bool(selected)
        if bool(self.property("selected")) == target:
            return
        self.setProperty("selected", target)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._theme_name)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (
            int(Qt.Key.Key_Return),
            int(Qt.Key.Key_Enter),
            int(Qt.Key.Key_Space),
        ):
            self.clicked.emit(self._theme_name)
            event.accept()
            return
        super().keyPressEvent(event)
