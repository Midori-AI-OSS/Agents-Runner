from __future__ import annotations

import os

from codex_local_conatinerd.agent_cli import normalize_agent
from codex_local_conatinerd.environments import serialize_environment
from codex_local_conatinerd.log_format import prettify_log_line
from codex_local_conatinerd.persistence import deserialize_task
from codex_local_conatinerd.persistence import load_state
from codex_local_conatinerd.persistence import save_state
from codex_local_conatinerd.persistence import serialize_task
from codex_local_conatinerd.ui.task_model import Task
from codex_local_conatinerd.ui.utils import _stain_color


class _MainWindowPersistenceMixin:
    def _schedule_save(self) -> None:
        self._save_timer.start()


    def _save_state(self) -> None:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at_s)
        environments = [serialize_environment(env) for env in self._environment_list()]
        payload = {"tasks": [serialize_task(t) for t in tasks], "settings": dict(self._settings_data), "environments": environments}
        save_state(self._state_path, payload)


    def _load_state(self) -> None:
        try:
            payload = load_state(self._state_path)
        except Exception:
            return
        settings = payload.get("settings")
        if isinstance(settings, dict):
            self._settings_data.update(settings)
        self._settings_data["use"] = normalize_agent(str(self._settings_data.get("use") or "codex"))
        try:
            self._settings_data["max_agents_running"] = int(str(self._settings_data.get("max_agents_running", -1)).strip())
        except Exception:
            self._settings_data["max_agents_running"] = -1
        self._settings_data.setdefault("host_claude_dir", "")
        self._settings_data.setdefault("host_copilot_dir", "")
        self._settings_data.setdefault("interactive_command_claude", "--add-dir /home/midori-ai/workspace")
        self._settings_data.setdefault("interactive_command_copilot", "--add-dir /home/midori-ai/workspace")
        host_codex_dir = os.path.normpath(os.path.expanduser(str(self._settings_data.get("host_codex_dir") or "").strip()))
        if host_codex_dir == os.path.expanduser("~/.midoriai"):
            self._settings_data["host_codex_dir"] = os.path.expanduser("~/.codex")
        for key in ("interactive_command", "interactive_command_claude", "interactive_command_copilot"):
            raw = str(self._settings_data.get(key) or "").strip()
            if not raw:
                continue
            self._settings_data[key] = self._sanitize_interactive_command_value(key, raw)
        items = payload.get("tasks") or []
        loaded: list[Task] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            task = deserialize_task(Task, item)
            if not task.task_id:
                continue
            if task.logs:
                task.logs = [prettify_log_line(line) for line in task.logs if isinstance(line, str)]
            loaded.append(task)
        loaded.sort(key=lambda t: t.created_at_s)
        for task in loaded:
            active = (task.status or "").lower() in {"queued", "pulling", "created", "running", "starting"}
            if active:
                task.status = "unknown"
            self._tasks[task.task_id] = task
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
