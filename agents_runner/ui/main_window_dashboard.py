from __future__ import annotations


from agents_runner.ui.utils import _stain_color


class _MainWindowDashboardMixin:
    def _refresh_task_rows(self) -> None:
        for task in self._tasks.values():
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _tick_dashboard_elapsed(self) -> None:
        if not self._dashboard.isVisible():
            return
        for task in self._tasks.values():
            if not task.is_active():
                continue
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
