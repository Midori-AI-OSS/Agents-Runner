from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPaintEvent, QPainter
from PySide6.QtWidgets import QScrollArea, QWidget


class _ScrollEdgeFadeOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScrollEdgeFadeOverlay")
        self._top_visible = False
        self._bottom_visible = False
        self._fade_px = 24
        self._fade_alpha = 48
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)

    def set_state(
        self, *, top_visible: bool, bottom_visible: bool, fade_px: int, fade_alpha: int
    ) -> None:
        top_visible = bool(top_visible)
        bottom_visible = bool(bottom_visible)
        fade_px = max(0, int(fade_px))
        fade_alpha = max(0, min(255, int(fade_alpha)))
        if (
            self._top_visible == top_visible
            and self._bottom_visible == bottom_visible
            and self._fade_px == fade_px
            and self._fade_alpha == fade_alpha
        ):
            return
        self._top_visible = top_visible
        self._bottom_visible = bottom_visible
        self._fade_px = fade_px
        self._fade_alpha = fade_alpha
        self.setVisible(self._top_visible or self._bottom_visible)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        if (
            not self._top_visible and not self._bottom_visible
        ) or self._fade_alpha <= 0:
            return

        width = int(self.width())
        height = int(self.height())
        if width <= 0 or height <= 0:
            return

        fade_px = int(min(max(self._fade_px, 0), max(0, height // 2)))
        if fade_px <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        color = QColor(0, 0, 0, self._fade_alpha)

        if self._top_visible:
            top_gradient = QLinearGradient(0, 0, 0, fade_px)
            top_gradient.setColorAt(0.0, color)
            top_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(0, 0, width, fade_px, top_gradient)

        if self._bottom_visible:
            bottom_gradient = QLinearGradient(0, height - fade_px, 0, height)
            bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
            bottom_gradient.setColorAt(1.0, color)
            painter.fillRect(0, height - fade_px, width, fade_px, bottom_gradient)


class EdgeFadeScrollArea(QScrollArea):
    """QScrollArea with conditional top/bottom edge fades."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        fade_px: int = 24,
        fade_alpha: int = 48,
    ) -> None:
        super().__init__(parent)
        self._fade_px = max(0, int(fade_px))
        self._fade_alpha = max(0, min(255, int(fade_alpha)))

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._overlay = _ScrollEdgeFadeOverlay(self.viewport())
        self._overlay.hide()
        self._overlay.raise_()

        scrollbar = self.verticalScrollBar()
        scrollbar.valueChanged.connect(self._sync_edge_fades)
        scrollbar.rangeChanged.connect(self._on_scroll_range_changed)
        self.viewport().installEventFilter(self)

        self._sync_overlay_geometry()
        self._sync_edge_fades()

    def setWidget(self, widget: QWidget) -> None:
        super().setWidget(widget)
        self._sync_overlay_geometry()
        self._sync_edge_fades()

    def set_fade_parameters(
        self, *, fade_px: int | None = None, fade_alpha: int | None = None
    ) -> None:
        if fade_px is not None:
            self._fade_px = max(0, int(fade_px))
        if fade_alpha is not None:
            self._fade_alpha = max(0, min(255, int(fade_alpha)))
        self._sync_edge_fades()

    def refresh_edge_fades(self) -> None:
        self._sync_edge_fades()

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self.viewport() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        ):
            self._sync_overlay_geometry()
            self._sync_edge_fades()
        return super().eventFilter(obj, event)

    def _sync_overlay_geometry(self) -> None:
        self._overlay.setGeometry(self.viewport().rect())
        self._overlay.raise_()

    def _on_scroll_range_changed(self, _minimum: int, _maximum: int) -> None:
        self._sync_edge_fades()

    def _sync_edge_fades(self, _value: int | None = None) -> None:
        scrollbar = self.verticalScrollBar()
        minimum = int(scrollbar.minimum())
        maximum = int(scrollbar.maximum())
        value = int(scrollbar.value())
        has_overflow = maximum > minimum
        show_top = has_overflow and value > minimum
        show_bottom = has_overflow and value < maximum
        self._overlay.set_state(
            top_visible=show_top,
            bottom_visible=show_bottom,
            fade_px=self._fade_px,
            fade_alpha=self._fade_alpha,
        )
