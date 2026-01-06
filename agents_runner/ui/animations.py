from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class AnimationPresets:
    """Standard animation durations and easing curves."""

    DURATION_FAST = 150
    DURATION_NORMAL = 250
    DURATION_SLOW = 350

    EASE_IN_OUT = QEasingCurve.Type.InOutCubic
    EASE_OUT = QEasingCurve.Type.OutCubic
    EASE_IN = QEasingCurve.Type.InCubic
    EASE_BOUNCE = QEasingCurve.Type.OutBack


def fade_in(
    widget: QWidget, duration: int = AnimationPresets.DURATION_NORMAL, delay: int = 0
) -> QPropertyAnimation:
    """Create a fade-in animation for a widget."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    effect.setOpacity(0.0)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(AnimationPresets.EASE_OUT)

    if delay > 0:
        seq = QSequentialAnimationGroup()
        seq.addPause(delay)
        seq.addAnimation(anim)
        return seq

    return anim


def fade_out(
    widget: QWidget, duration: int = AnimationPresets.DURATION_NORMAL
) -> QPropertyAnimation:
    """Create a fade-out animation for a widget."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(AnimationPresets.EASE_IN)

    return anim


def cross_fade(
    hide_widget: QWidget,
    show_widget: QWidget,
    duration: int = AnimationPresets.DURATION_NORMAL,
) -> QParallelAnimationGroup:
    """Cross-fade between two widgets."""
    group = QParallelAnimationGroup()

    fade_out_anim = fade_out(hide_widget, duration)
    fade_out_anim.finished.connect(hide_widget.hide)
    group.addAnimation(fade_out_anim)

    show_widget.show()
    fade_in_anim = fade_in(show_widget, duration)
    group.addAnimation(fade_in_anim)

    return group


def slide_fade_in(
    widget: QWidget,
    direction: str = "up",
    duration: int = AnimationPresets.DURATION_NORMAL,
    distance: int = 30,
) -> QParallelAnimationGroup:
    """Slide and fade in a widget from a direction."""
    group = QParallelAnimationGroup()

    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(0.0)

    fade_anim = QPropertyAnimation(effect, b"opacity")
    fade_anim.setDuration(duration)
    fade_anim.setStartValue(0.0)
    fade_anim.setEndValue(1.0)
    fade_anim.setEasingCurve(AnimationPresets.EASE_OUT)
    group.addAnimation(fade_anim)

    start_pos = widget.pos()
    if direction == "up":
        offset_pos = start_pos + Qt.QPoint(0, distance)
    elif direction == "down":
        offset_pos = start_pos - Qt.QPoint(0, distance)
    elif direction == "left":
        offset_pos = start_pos + Qt.QPoint(distance, 0)
    else:
        offset_pos = start_pos - Qt.QPoint(distance, 0)

    widget.move(offset_pos)

    pos_anim = QPropertyAnimation(widget, b"pos")
    pos_anim.setDuration(duration)
    pos_anim.setStartValue(offset_pos)
    pos_anim.setEndValue(start_pos)
    pos_anim.setEasingCurve(AnimationPresets.EASE_OUT)
    group.addAnimation(pos_anim)

    return group


def staggered_fade_in(
    widgets: list[QWidget],
    base_duration: int = AnimationPresets.DURATION_NORMAL,
    stagger_delay: int = 50,
) -> QParallelAnimationGroup:
    """Fade in multiple widgets with a staggered delay."""
    group = QParallelAnimationGroup()

    for idx, widget in enumerate(widgets):
        anim = fade_in(widget, base_duration, delay=idx * stagger_delay)
        group.addAnimation(anim)

    return group


class AnimatedButton:
    """Mix-in or helper to add hover/press animations to buttons."""

    @staticmethod
    def setup_button_animations(button: QWidget) -> None:
        """Add event filter for button hover/press effects."""
        button.installEventFilter(_ButtonAnimationFilter(button))


class _ButtonAnimationFilter:
    """Internal event filter for button animations."""

    def __init__(self, button: QWidget) -> None:
        self._button = button
        self._hover_anim: QPropertyAnimation | None = None
        self._press_anim: QPropertyAnimation | None = None
        self._original_style = button.styleSheet()

    def eventFilter(self, obj: QWidget, event) -> bool:
        if obj != self._button:
            return False

        event_type = event.type()

        if event_type == event.Type.Enter:
            self._on_hover_enter()
        elif event_type == event.Type.Leave:
            self._on_hover_leave()
        elif event_type == event.Type.MouseButtonPress:
            self._on_press()
        elif event_type == event.Type.MouseButtonRelease:
            self._on_release()

        return False

    def _on_hover_enter(self) -> None:
        if self._hover_anim:
            self._hover_anim.stop()

        style = self._button.styleSheet()
        if "background" not in style:
            style = (
                self._original_style
                + "\nQToolButton:hover { background-color: rgba(255, 255, 255, 20); }"
            )
            self._button.setStyleSheet(style)

    def _on_hover_leave(self) -> None:
        if self._hover_anim:
            self._hover_anim.stop()

    def _on_press(self) -> None:
        pass

    def _on_release(self) -> None:
        pass
