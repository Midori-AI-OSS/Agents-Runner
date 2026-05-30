from __future__ import annotations

from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QEvent
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import QSize
from PySide6.QtCore import QSignalBlocker
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import QVariantAnimation
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
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
    COLLAPSE_DELAY_MS = 3000
    PLAY_BUTTON_WIDTH = 40
    PLAY_BUTTON_HEIGHT = 40
    VOLUME_RIGHT_GAP = 8
    ICON_COLOR_PLAYING = (16, 185, 129)
    ICON_COLOR_IDLE = (239, 68, 68)
    ICON_COLOR_RECONNECT_START = (250, 204, 21)
    ICON_COLOR_RECONNECT_END = (76, 29, 149)
    RECONNECT_ANIMATION_MS = 900
    CONNECTION_STATES = ("unavailable", "idle", "playing", "reconnecting")
    COLLAPSED_VOLUME_WIDTH = max(0, COLLAPSED_WIDTH - PLAY_BUTTON_WIDTH)
    EXPANDED_VOLUME_WIDTH = max(COLLAPSED_VOLUME_WIDTH, EXPANDED_WIDTH - PLAY_BUTTON_WIDTH)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadioControlRoot")
        self.setFixedHeight(self.PLAY_BUTTON_HEIGHT)
        self.setMinimumWidth(self.COLLAPSED_WIDTH)
        self.setMaximumWidth(self.COLLAPSED_WIDTH)

        self._expanded = False
        self._drag_active = False
        self._service_available = False
        self._is_playing = False
        self._radio_enabled = False
        self._connection_state = "idle"
        self._reconnect_anim_value = 0.0
        self._status_text = "Radio unavailable."

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._volume_section = QWidget(self)
        self._volume_section.setFixedHeight(self.PLAY_BUTTON_HEIGHT)
        self._volume_section.setMinimumWidth(self.COLLAPSED_VOLUME_WIDTH)
        self._volume_section.setMaximumWidth(self.COLLAPSED_VOLUME_WIDTH)
        volume_section_layout = QHBoxLayout(self._volume_section)
        volume_section_layout.setContentsMargins(0, 0, self.VOLUME_RIGHT_GAP, 0)
        volume_section_layout.setSpacing(0)

        self._slider_wrap = QWidget(self._volume_section)
        self._slider_wrap.setObjectName("RadioControlSliderWrap")
        self._slider_wrap.setFixedHeight(self.PLAY_BUTTON_HEIGHT)
        slider_layout = QHBoxLayout(self._slider_wrap)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_layout.setSpacing(0)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal, self._slider_wrap)
        self._volume_slider.setObjectName("RadioControlVolumeSlider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.valueChanged.connect(self.volume_changed.emit)
        self._volume_slider.sliderPressed.connect(self._on_slider_pressed)
        self._volume_slider.sliderReleased.connect(self._on_slider_released)
        slider_layout.addWidget(self._volume_slider, 1)
        volume_section_layout.addWidget(self._slider_wrap, 1)

        self._play_section = QWidget(self)
        self._play_section.setFixedSize(self.PLAY_BUTTON_WIDTH, self.PLAY_BUTTON_HEIGHT)
        play_section_layout = QHBoxLayout(self._play_section)
        play_section_layout.setContentsMargins(0, 0, 0, 0)
        play_section_layout.setSpacing(0)

        self._play_button = QToolButton(self._play_section)
        self._play_button.setObjectName("RadioControlButton")
        self._play_button.setIconSize(QSize(18, 18))
        self._play_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._play_button.setAutoRaise(False)
        self._play_button.setCheckable(True)
        self._play_button.setFixedSize(self.PLAY_BUTTON_WIDTH, self.PLAY_BUTTON_HEIGHT)
        self._play_button.clicked.connect(self.play_requested.emit)
        play_section_layout.addWidget(self._play_button, 0, Qt.AlignmentFlag.AlignCenter)

        root.addStretch(1)
        root.addWidget(self._volume_section, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self._play_section, 0, Qt.AlignmentFlag.AlignVCenter)

        self._slider_opacity_effect = QGraphicsOpacityEffect(self._slider_wrap)
        self._slider_wrap.setGraphicsEffect(self._slider_opacity_effect)
        self._slider_opacity_effect.setOpacity(0.0)

        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(self.COLLAPSE_DELAY_MS)
        self._collapse_timer.timeout.connect(self._on_collapse_timeout)

        self._volume_width_anim = QPropertyAnimation(
            self._volume_section,
            b"maximumWidth",
            self,
        )
        self._volume_width_anim.setDuration(self.ANIMATION_MS)
        self._volume_width_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._volume_width_anim.valueChanged.connect(self._sync_volume_min_width)
        self._volume_width_anim.finished.connect(self._on_volume_width_animation_finished)

        self._opacity_anim = QPropertyAnimation(self._slider_opacity_effect, b"opacity", self)
        self._opacity_anim.setDuration(self.ANIMATION_MS)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._reconnect_anim = QVariantAnimation(self)
        self._reconnect_anim.setDuration(self.RECONNECT_ANIMATION_MS)
        self._reconnect_anim.setStartValue(0.0)
        self._reconnect_anim.setKeyValueAt(0.5, 1.0)
        self._reconnect_anim.setEndValue(0.0)
        self._reconnect_anim.setLoopCount(-1)
        self._reconnect_anim.valueChanged.connect(self._on_reconnect_animation_value_changed)

        for watched in (
            self,
            self._play_section,
            self._play_button,
            self._volume_section,
            self._slider_wrap,
            self._volume_slider,
        ):
            watched.installEventFilter(self)

        self._refresh_play_button_icon()
        self._refresh_tooltip()
        self._refresh_interaction_enabled()

    def set_service_available(self, available: bool) -> None:
        self._service_available = bool(available)
        self._refresh_interaction_enabled()
        self._refresh_tooltip()

    def set_playing(self, playing: bool) -> None:
        self._is_playing = bool(playing)
        self._play_button.setChecked(self._is_playing)
        self._refresh_play_button_icon()
        self._refresh_tooltip()

    def set_radio_enabled(self, enabled: bool) -> None:
        self._radio_enabled = bool(enabled)
        self._refresh_tooltip()

    def set_connection_state(self, state: str) -> None:
        normalized = str(state or "").strip().lower()
        if normalized not in self.CONNECTION_STATES:
            normalized = "idle"
        if normalized == self._connection_state:
            return
        self._connection_state = normalized
        if normalized == "reconnecting":
            self._start_reconnect_animation()
        else:
            self._stop_reconnect_animation()
        self._refresh_play_button_icon()
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
        elif self._connection_state == "reconnecting":
            tooltip = "Reconnecting Midori AI Radio."
        elif self._is_playing:
            tooltip = "Turn off Midori AI Radio."
        elif self._radio_enabled:
            tooltip = "Start Midori AI Radio."
        else:
            tooltip = "Start Midori AI Radio and enable the radio system."
        self._play_button.setToolTip(tooltip)
        self.setToolTip(tooltip)

    def _refresh_play_button_icon(self) -> None:
        if self._connection_state == "reconnecting":
            color = self._interpolated_reconnect_color(self._reconnect_anim_value)
        elif self._connection_state == "playing" or self._is_playing:
            color = QColor(*self.ICON_COLOR_PLAYING)
        else:
            color = QColor(*self.ICON_COLOR_IDLE)
        self._play_button.setIcon(
            lucide_icon(
                "audio-lines",
                color=color,
            )
        )

    def _start_reconnect_animation(self) -> None:
        if self._reconnect_anim.state() == QVariantAnimation.State.Running:
            return
        self._reconnect_anim.start()

    def _stop_reconnect_animation(self) -> None:
        if self._reconnect_anim.state() == QVariantAnimation.State.Running:
            self._reconnect_anim.stop()
        self._reconnect_anim_value = 0.0

    def _on_reconnect_animation_value_changed(self, value: object) -> None:
        try:
            parsed = float(value)
        except Exception:
            return
        self._reconnect_anim_value = max(0.0, min(1.0, parsed))
        if self._connection_state == "reconnecting":
            self._refresh_play_button_icon()

    def _interpolated_reconnect_color(self, progress: float) -> QColor:
        clamped = max(0.0, min(1.0, float(progress)))
        start_r, start_g, start_b = self.ICON_COLOR_RECONNECT_START
        end_r, end_g, end_b = self.ICON_COLOR_RECONNECT_END
        red = int(round(start_r + ((end_r - start_r) * clamped)))
        green = int(round(start_g + ((end_g - start_g) * clamped)))
        blue = int(round(start_b + ((end_b - start_b) * clamped)))
        return QColor(red, green, blue)

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
        if self._is_interaction_active():
            self._collapse_timer.stop()
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
            or self._play_section.underMouse()
            or self._play_button.underMouse()
            or self._volume_section.underMouse()
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
        self._volume_width_anim.stop()
        self._opacity_anim.stop()
        self._set_root_width(self.EXPANDED_WIDTH)

        current_volume_width = int(self._volume_section.maximumWidth())
        target_volume_width = self.EXPANDED_VOLUME_WIDTH if expanded else self.COLLAPSED_VOLUME_WIDTH
        self._volume_width_anim.setStartValue(current_volume_width)
        self._volume_width_anim.setEndValue(target_volume_width)
        self._volume_width_anim.start()

        start_opacity = float(self._slider_opacity_effect.opacity())
        target_opacity = 1.0 if expanded else 0.0
        self._opacity_anim.setStartValue(start_opacity)
        self._opacity_anim.setEndValue(target_opacity)
        self._opacity_anim.start()

    def _sync_volume_min_width(self, value: object) -> None:
        try:
            width = int(value)
        except Exception:
            return
        self._volume_section.setMinimumWidth(width)

    def _on_volume_width_animation_finished(self) -> None:
        if self._expanded:
            return
        self._set_root_width(self.COLLAPSED_WIDTH)

    def _set_root_width(self, width: int) -> None:
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
