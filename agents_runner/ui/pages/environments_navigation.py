from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QSignalBlocker,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect

from agents_runner.ui.constants import LEFT_NAV_COMPACT_THRESHOLD


class _EnvironmentsNavigationMixin:
    def _on_back(self) -> None:
        if not self.try_autosave():
            return
        self.back_requested.emit()

    def _connect_autosave_signals(self) -> None:
        for combo in (
            self._color,
            self._workspace_type_combo,
        ):
            combo.currentIndexChanged.connect(self._trigger_immediate_autosave)

        for checkbox in (
            self._headless_desktop_enabled,
            self._cache_desktop_build,
            self._container_caching_enabled,
            self._use_cross_agents,
            self._gh_context_enabled,
            self._gh_use_host_cli,
            self._preflight_enabled,
            self._cache_system_preflight_enabled,
            self._cache_settings_preflight_enabled,
        ):
            checkbox.toggled.connect(self._trigger_immediate_autosave)

        for line_edit in (
            self._name,
            self._max_agents_running,
            self._workspace_target,
        ):
            line_edit.textChanged.connect(self._queue_debounced_autosave)

        self._preflight_script.textChanged.connect(self._queue_debounced_autosave)

    def _on_nav_button_clicked(self, key: str) -> None:
        self._navigate_to_pane(key, user_initiated=True)

    def _on_compact_nav_changed(self, _index: int) -> None:
        key = str(self._compact_nav.currentData() or "").strip()
        if not key:
            return
        self._navigate_to_pane(key, user_initiated=True)

    def _navigate_to_pane(self, key: str, *, user_initiated: bool) -> None:
        key = str(key or "").strip()
        if not key or key not in self._pane_index_by_key:
            return
        if key == self._active_pane_key:
            self._set_active_navigation(key)
            return

        if user_initiated and not self.try_autosave():
            self._set_active_navigation(self._active_pane_key)
            return

        self._set_current_pane(key, animate=True)
        self._set_active_navigation(key)

    def _set_active_navigation(self, key: str) -> None:
        self._active_pane_key = key
        for pane_key, button in self._nav_buttons.items():
            button.setChecked(pane_key == key)

        idx = self._compact_nav.findData(key)
        if idx >= 0:
            with QSignalBlocker(self._compact_nav):
                self._compact_nav.setCurrentIndex(idx)

    def _set_current_pane(self, key: str, *, animate: bool) -> None:
        target_index = self._pane_index_by_key.get(key)
        if target_index is None:
            return

        current_index = self._page_stack.currentIndex()
        if current_index == target_index:
            self._active_pane_key = key
            return

        if current_index < 0 or not animate:
            self._page_stack.setCurrentIndex(target_index)
            self._active_pane_key = key
            return

        forward = target_index > current_index
        self._page_stack.setCurrentIndex(target_index)
        self._animate_stack(forward=forward)
        self._active_pane_key = key

    def _animate_stack(self, *, forward: bool) -> None:
        if self._pane_animation is not None:
            self._pane_animation.stop()
            self._pane_animation = None

        if self._pane_rest_pos is not None:
            self._page_stack.move(self._pane_rest_pos)
        self._page_stack.setGraphicsEffect(None)

        base_pos = self._page_stack.pos()
        self._pane_rest_pos = QPoint(base_pos)

        offset = 16 if forward else -16
        start_pos = QPoint(base_pos.x() + offset, base_pos.y())

        effect = QGraphicsOpacityEffect(self._page_stack)
        effect.setOpacity(0.0)
        self._page_stack.setGraphicsEffect(effect)
        self._page_stack.move(start_pos)

        pos_anim = QPropertyAnimation(self._page_stack, b"pos", self)
        pos_anim.setDuration(210)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(base_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        opacity_anim = QPropertyAnimation(effect, b"opacity", self)
        opacity_anim.setDuration(210)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)

        def _cleanup() -> None:
            if self._pane_rest_pos is not None:
                self._page_stack.move(self._pane_rest_pos)
            self._page_stack.setGraphicsEffect(None)
            self._pane_animation = None

        group.finished.connect(_cleanup)
        group.start()
        self._pane_animation = group

    def _queue_debounced_autosave(self, *_args: object) -> None:
        if self._suppress_autosave:
            return
        self._autosave_timer.start()

    def _trigger_immediate_autosave(self, *_args: object) -> None:
        if self._suppress_autosave:
            return
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        self._emit_autosave()

    def _emit_autosave(self) -> None:
        if self._suppress_autosave:
            return
        self.try_autosave(show_validation_errors=False)

    def _update_navigation_mode(self) -> None:
        compact = self.width() < LEFT_NAV_COMPACT_THRESHOLD
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        self._compact_nav.setVisible(compact)
        self._nav_panel.setVisible(not compact)
