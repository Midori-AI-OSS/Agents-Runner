from __future__ import annotations

from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QEvent
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import QSignalBlocker
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QSlider
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QWidget

from agents_runner.ui.lucide_icons import lucide_icon


class RadioControlWidget(QWidget):
    """Compact navbar control for Midori AI Radio playback + volume."""

    play_requested = Signal()
    volume_changed = Signal(int)

    COLLAPSED_WIDTH = 44
    EXPANDED_WIDTH = 230
    ANIMATION_MS = 170
    COLLAPSE_DELAY_MS = 350

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadioControlRoot")
        self.setFixedHeight(40)
        self.setMinimumWidth(self.COLLAPSED_WIDTH)
        self.setMaximumWidth(self.COLLAPSED_WIDTH)

        self._expanded = False
        self._drag_active = False
        self._service_available = False
        self._is_playing = False
        self._radio_enabled = False
        self._status_text = "Radio unavailable."

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._play_button = QToolButton(self)
        self._play_button.setObjectName("RadioControlButton")
        self._play_button.setIcon(lucide_icon("audio-lines"))
        self._play_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._play_button.setAutoRaise(False)
        self._play_button.setCheckable(True)
        self._play_button.setFixedSize(40, 40)
        self._play_button.clicked.connect(self.play_requested.emit)
        root.addWidget(self._play_button)

        self._slider_wrap = QWidget(self)
        self._slider_wrap.setObjectName("RadioControlSliderWrap")
        self._slider_wrap.setFixedHeight(40)
        slider_layout = QHBoxLayout(self._slider_wrap)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_layout.setSpacing(0)

        self._volume_slider = QSlider(Qt.Horizontal, self._slider_wrap)
        self._volume_slider.setObjectName("RadioControlVolumeSlider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.valueChanged.connect(self.volume_changed.emit)
        self._volume_slider.sliderPressed.connect(self._on_slider_pressed)
        self._volume_slider.sliderReleased.connect(self._on_slider_released)
        slider_layout.addWidget(self._volume_slider, 1)
        root.addWidget(self._slider_wrap, 1)

        self._slider_opacity_effect = QGraphicsOpacityEffect(self._slider_wrap)
        self._slider_wrap.setGraphicsEffect(self._slider_opacity_effect)
        self._slider_opacity_effect.setOpacity(0.0)
        self._slider_wrap.setVisible(False)

        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(self.COLLAPSE_DELAY_MS)
        self._collapse_timer.timeout.connect(self._on_collapse_timeout)

        self._width_anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._width_anim.setDuration(self.ANIMATION_MS)
        self._width_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._width_anim.valueChanged.connect(self._sync_min_width)

        self._opacity_anim = QPropertyAnimation(
            self._slider_opacity_effect, b"opacity", self
        )
        self._opacity_anim.setDuration(self.ANIMATION_MS)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._opacity_anim.finished.connect(self._on_opacity_animation_finished)

        for watched in (
            self,
            self._play_button,
            self._slider_wrap,
            self._volume_slider,
        ):
            watched.installEventFilter(self)

        self._refresh_tooltip()
        self._refresh_interaction_enabled()

    def set_service_available(self, available: bool) -> None:
        self._service_available = bool(available)
        self._refresh_interaction_enabled()
        self._refresh_tooltip()

    def set_playing(self, playing: bool) -> None:
        self._is_playing = bool(playing)
        self._play_button.setChecked(self._is_playing)
        self._refresh_tooltip()

    def set_radio_enabled(self, enabled: bool) -> None:
        self._radio_enabled = bool(enabled)
        self._refresh_tooltip()

    def set_volume(self, value: int) -> None:
        clamped = max(0, min(100, int(value)))
        with QSignalBlocker(self._volume_slider):
            self._volume_slider.setValue(clamped)

    def set_status_tooltip(self, text: str) -> None:
        self._status_text = str(text or "").strip() or "Radio unavailable."
        self._refresh_tooltip()

    def _refresh_interaction_enabled(self) -> None:
        available = self._service_available
        self._play_button.setEnabled(available)
        self._volume_slider.setEnabled(available)
        if not available:
            self._collapse_timer.stop()
            self._set_expanded(False)

    def _refresh_tooltip(self) -> None:
        if not self._service_available:
            tooltip = self._status_text or "Midori AI Radio is currently unavailable."
        elif self._is_playing:
            tooltip = "Stop Midori AI Radio."
        elif self._radio_enabled:
            tooltip = "Start Midori AI Radio."
        else:
            tooltip = "Start Midori AI Radio and enable the radio system."
        self._play_button.setToolTip(tooltip)
        self.setToolTip(tooltip)

    def _on_slider_pressed(self) -> None:
        self._drag_active = True
        self._collapse_timer.stop()
        self._set_expanded(True)

    def _on_slider_released(self) -> None:
        self._drag_active = False
        self._schedule_collapse()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        event_type = event.type()

        if event_type in (QEvent.Type.Enter, QEvent.Type.FocusIn):
            self._collapse_timer.stop()
            self._set_expanded(True)
        elif event_type in (QEvent.Type.Leave, QEvent.Type.FocusOut):
            self._schedule_collapse()

        return super().eventFilter(watched, event)

    def _schedule_collapse(self) -> None:
        if self._drag_active:
            return
        self._collapse_timer.start()

    def _on_collapse_timeout(self) -> None:
        if self._drag_active:
            return
        if self._is_interaction_active():
            return
        self._set_expanded(False)

    def _is_interaction_active(self) -> bool:
        if (
            self.underMouse()
            or self._play_button.underMouse()
            or self._slider_wrap.underMouse()
        ):
            return True
        if self._play_button.hasFocus() or self._volume_slider.hasFocus():
            return True
        return False

    def _set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return

        self._expanded = expanded
        self._width_anim.stop()
        self._opacity_anim.stop()

        if expanded:
            self._slider_wrap.setVisible(True)

        current_max_width = int(self.maximumWidth())
        target_width = self.EXPANDED_WIDTH if expanded else self.COLLAPSED_WIDTH

        self._width_anim.setStartValue(current_max_width)
        self._width_anim.setEndValue(target_width)
        self._width_anim.start()

        start_opacity = float(self._slider_opacity_effect.opacity())
        target_opacity = 1.0 if expanded else 0.0
        self._opacity_anim.setStartValue(start_opacity)
        self._opacity_anim.setEndValue(target_opacity)
        self._opacity_anim.start()

    def _sync_min_width(self, value: object) -> None:
        try:
            width = int(value)
        except Exception:
            return
        self.setMinimumWidth(width)

    def _on_opacity_animation_finished(self) -> None:
        if self._expanded:
            return
        self._slider_wrap.setVisible(False)
