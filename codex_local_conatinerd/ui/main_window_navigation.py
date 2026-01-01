from __future__ import annotations

from PySide6.QtWidgets import QMessageBox


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


    def _show_dashboard(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._dashboard.show()


    def _show_new_task(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._new_task.focus_prompt()
        self._new_task.show()


    def _show_task_details(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._new_task.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._details.show()


    def _show_environments(self) -> None:
        if self._envs_page.isVisible():
            return
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._new_task.hide()
        self._details.hide()
        self._settings.hide()
        self._envs_page.set_environments(self._environments, self._active_environment_id())
        self._envs_page.show()


    def _show_settings(self) -> None:
        if self._settings.isVisible():
            return
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.set_settings(self._settings_data)
        self._settings.show()


    def _try_autosave_before_navigation(self) -> bool:
        if self._envs_page.isVisible() and not self._envs_page.try_autosave():
            return False
        if self._settings.isVisible() and not self._settings.try_autosave():
            return False
        return True
