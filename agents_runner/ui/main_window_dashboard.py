from __future__ import annotations

import time

from agents_runner.log_format import prettify_log_line
from agents_runner.persistence import deserialize_task
from agents_runner.persistence import load_done_task_payloads
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color


PAST_TASK_PAGE_SIZE = 10


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


    def _load_more_past_tasks(self, offset: int) -> None:
        try:
            offset = max(0, int(offset))
        except Exception:
            offset = 0

        payloads = load_done_task_payloads(self._state_path, offset=offset, limit=PAST_TASK_PAGE_SIZE)
        loaded = 0
        for item in payloads:
            if not isinstance(item, dict):
                continue
            task = deserialize_task(Task, item)
            if not task.task_id:
                continue
            if task.logs:
                task.logs = [prettify_log_line(line) for line in task.logs if isinstance(line, str)]
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            self._dashboard.upsert_past_task(task, stain=stain)
            loaded += 1

        if loaded == 0 and offset == 0:
            self._dashboard.set_past_load_more_enabled(False, "No past tasks")
            return

        if loaded < PAST_TASK_PAGE_SIZE:
            self._dashboard.set_past_load_more_enabled(False, "No more tasks")
            return

        self._dashboard.set_past_load_more_enabled(True)
