from __future__ import annotations


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

    def _load_past_tasks_batch(self, offset: int, limit: int) -> int:
        """Load a batch of past tasks.

        Args:
            offset: Starting offset for loading.
            limit: Maximum number of tasks to load.

        Returns:
            Number of tasks successfully loaded.
        """
        try:
            offset = max(0, int(offset))
        except Exception:
            offset = 0

        try:
            limit = max(1, int(limit))
        except Exception:
            limit = PAST_TASK_PAGE_SIZE

        payloads = load_done_task_payloads(self._state_path, offset=offset, limit=limit)
        loaded = 0
        for item in payloads:
            if not isinstance(item, dict):
                continue
            task = deserialize_task(Task, item)
            if not task.task_id:
                continue
            if task.logs:
                task.logs = [
                    prettify_log_line(line)
                    for line in task.logs
                    if isinstance(line, str)
                ]
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            self._dashboard.upsert_past_task(task, stain=stain)
            loaded += 1

        return loaded
