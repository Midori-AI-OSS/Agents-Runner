from __future__ import annotations

import os

from agents_runner.agent_cli import normalize_agent
from agents_runner.environments import serialize_environment
from agents_runner.log_format import prettify_log_line
from agents_runner.persistence import deserialize_task
from agents_runner.persistence import load_active_task_payloads
from agents_runner.persistence import load_state
from agents_runner.persistence import save_task_payload
from agents_runner.persistence import save_state
from agents_runner.persistence import serialize_task
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _parse_docker_time
from agents_runner.ui.utils import _stain_color


class _MainWindowPersistenceMixin:
    @staticmethod
    def _should_archive_task(task: Task) -> bool:
        status = (task.status or "").lower()
        if status == "discarded":
            return True
        return task.is_done() or task.is_failed()

    @staticmethod
    def _try_sync_container_state(task: Task) -> bool:
        container_id = str(task.container_id or "").strip()
        if not container_id:
            return False
        try:
            from agents_runner.docker.process import _inspect_state
        except Exception:
            return False
        try:
            state = _inspect_state(container_id)
        except Exception:
            return False
        if not isinstance(state, dict) or not state:
            return False

        incoming = str(state.get("Status") or "").strip().lower()
        if incoming:
            task.status = incoming

        started_at = _parse_docker_time(state.get("StartedAt"))
        finished_at = _parse_docker_time(state.get("FinishedAt"))
        if started_at:
            task.started_at = started_at
        if finished_at:
            task.finished_at = finished_at

        exit_code = state.get("ExitCode")
        if exit_code is not None:
            try:
                task.exit_code = int(exit_code)
            except Exception:
                pass
        return True

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _save_state(self) -> None:
        environments = [serialize_environment(env) for env in self._environment_list()]
        payload = {"settings": dict(self._settings_data), "environments": environments}
        save_state(self._state_path, payload)
        for task in sorted(self._tasks.values(), key=lambda t: t.created_at_s):
            save_task_payload(
                self._state_path,
                serialize_task(task),
                archived=self._should_archive_task(task),
            )

    def _load_state(self) -> None:
        try:
            payload = load_state(self._state_path)
        except Exception:
            return
        settings = payload.get("settings")
        if isinstance(settings, dict):
            self._settings_data.update(settings)
        self._settings_data["use"] = normalize_agent(
            str(self._settings_data.get("use") or "codex")
        )
        try:
            self._settings_data["max_agents_running"] = int(
                str(self._settings_data.get("max_agents_running", -1)).strip()
            )
        except Exception:
            self._settings_data["max_agents_running"] = -1
        self._settings_data.setdefault(
            "host_claude_dir", os.path.expanduser("~/.claude")
        )
        self._settings_data.setdefault(
            "host_copilot_dir", os.path.expanduser("~/.copilot")
        )
        self._settings_data.setdefault(
            "host_gemini_dir", os.path.expanduser("~/.gemini")
        )
        self._settings_data.setdefault(
            "interactive_command_claude", "--add-dir /home/midori-ai/workspace"
        )
        self._settings_data.setdefault(
            "interactive_command_copilot",
            "--allow-all-tools --allow-all-paths --add-dir /home/midori-ai/workspace",
        )
        self._settings_data.setdefault(
            "interactive_command_gemini",
            "--no-sandbox --approval-mode yolo --include-directories /home/midori-ai/workspace",
        )
        host_codex_dir = os.path.normpath(
            os.path.expanduser(
                str(self._settings_data.get("host_codex_dir") or "").strip()
            )
        )
        if host_codex_dir == os.path.expanduser("~/.midoriai"):
            self._settings_data["host_codex_dir"] = os.path.expanduser("~/.codex")
        if not str(self._settings_data.get("host_codex_dir") or "").strip():
            self._settings_data["host_codex_dir"] = os.environ.get(
                "CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex")
            )
        if not str(self._settings_data.get("host_claude_dir") or "").strip():
            self._settings_data["host_claude_dir"] = os.path.expanduser("~/.claude")
        if not str(self._settings_data.get("host_copilot_dir") or "").strip():
            self._settings_data["host_copilot_dir"] = os.path.expanduser("~/.copilot")
        if not str(self._settings_data.get("host_gemini_dir") or "").strip():
            self._settings_data["host_gemini_dir"] = os.path.expanduser("~/.gemini")
        for key in (
            "interactive_command",
            "interactive_command_claude",
            "interactive_command_copilot",
            "interactive_command_gemini",
        ):
            raw = str(self._settings_data.get(key) or "").strip()
            if not raw:
                continue
            self._settings_data[key] = self._sanitize_interactive_command_value(
                key, raw
            )

        items = load_active_task_payloads(self._state_path)
        loaded: list[Task] = []
        for item in items:
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
            status = (task.status or "").lower()
            synced = False
            if status != "queued":
                synced = self._try_sync_container_state(task)
            if self._should_archive_task(task):
                save_task_payload(self._state_path, serialize_task(task), archived=True)
                continue
            if not synced and task.is_active() and status != "queued":
                task.status = "unknown"
            loaded.append(task)
        loaded.sort(key=lambda t: t.created_at_s)
        for task in loaded:
            self._tasks[task.task_id] = task
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
