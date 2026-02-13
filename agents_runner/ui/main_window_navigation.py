from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect


class _MainWindowNavigationMixin:
    def _apply_window_prefs(self) -> None:
        try:
            w = int(self._settings_data.get("window_w") or 1280)
            h = int(self._settings_data.get("window_h") or 720)
        except Exception:
            w, h = 1280, 720
        w = max(int(self.minimumWidth()), w)
        h = max(int(self.minimumHeight()), h)
        self.resize(w, h)

    def _transition_to_page(self, target_page) -> None:
        """Smooth cross-fade transition between pages."""
        pages = [
            self._dashboard,
            self._tasks_page,
            self._details,
            self._envs_page,
            self._settings,
        ]
        current_page = None

        for page in pages:
            if page.isVisible() and page != target_page:
                current_page = page
                break

        if current_page is None:
            target_page.show()
            return

        # Prime hidden page geometry to avoid first-frame size pop during cross-fade.
        try:
            target_page.setGeometry(current_page.geometry())
            target_page.updateGeometry()
        except Exception:
            pass

        effect_out = current_page.graphicsEffect()
        if not isinstance(effect_out, QGraphicsOpacityEffect):
            effect_out = QGraphicsOpacityEffect(current_page)
            current_page.setGraphicsEffect(effect_out)
        effect_out.setOpacity(1.0)

        effect_in = target_page.graphicsEffect()
        if not isinstance(effect_in, QGraphicsOpacityEffect):
            effect_in = QGraphicsOpacityEffect(target_page)
            target_page.setGraphicsEffect(effect_in)
        effect_in.setOpacity(0.0)

        anim_in = QPropertyAnimation(effect_in, b"opacity", self)
        anim_in.setDuration(200)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)

        anim_out = QPropertyAnimation(effect_out, b"opacity", self)
        anim_out.setDuration(150)
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)

        def _cleanup_effects() -> None:
            if current_page.graphicsEffect() is effect_out:
                current_page.setGraphicsEffect(None)
            if target_page.graphicsEffect() is effect_in:
                target_page.setGraphicsEffect(None)
            animations = getattr(self, "_page_animations", None)
            if isinstance(animations, list):
                for anim in (anim_out, anim_in):
                    try:
                        animations.remove(anim)
                    except ValueError:
                        pass

        def start_fade_in() -> None:
            current_page.hide()
            try:
                target_page.setGeometry(current_page.geometry())
                target_page.updateGeometry()
            except Exception:
                pass
            target_page.show()
            anim_in.start()

        anim_out.finished.connect(start_fade_in)
        anim_in.finished.connect(_cleanup_effects)

        anim_out.start()

        if not hasattr(self, "_page_animations"):
            self._page_animations = []
        self._page_animations.append(anim_out)
        self._page_animations.append(anim_in)

    def _show_dashboard(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._transition_to_page(self._dashboard)

    def _should_auto_navigate_on_task_start(self, *, interactive: bool) -> bool:
        key = (
            "auto_navigate_on_run_interactive_start"
            if interactive
            else "auto_navigate_on_run_agent_start"
        )
        return bool(self._settings_data.get(key) or False)

    def _maybe_auto_navigate_on_task_start(self, *, interactive: bool) -> None:
        if self._should_auto_navigate_on_task_start(interactive=interactive):
            self._show_dashboard()

    def _show_new_task(self) -> None:
        self._show_tasks()

    def _show_tasks(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._tasks_page.show_new_task_tab(focus_prompt=True)
        self._transition_to_page(self._tasks_page)

    def _show_task_details(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._transition_to_page(self._details)

    def _show_environments(self) -> None:
        if self._envs_page.isVisible():
            return
        if not self._try_autosave_before_navigation():
            return
        active_id = self._active_environment_id()
        if hasattr(
            self, "_is_internal_environment_id"
        ) and self._is_internal_environment_id(active_id):
            active_id = "default"
        self._envs_page.set_environments(self._user_environment_map(), active_id)
        self._transition_to_page(self._envs_page)

    def _show_settings(self) -> None:
        if self._settings.isVisible():
            return
        if not self._try_autosave_before_navigation():
            return
        self._settings.set_settings(self._settings_data)
        if hasattr(self, "_refresh_radio_channel_options"):
            self._refresh_radio_channel_options(disable_on_failure=True)
        self._transition_to_page(self._settings)

    def _try_autosave_before_navigation(self) -> bool:
        if self._envs_page.isVisible() and not self._envs_page.try_autosave():
            return False
        if self._settings.isVisible() and not self._settings.try_autosave():
            return False
        return True
