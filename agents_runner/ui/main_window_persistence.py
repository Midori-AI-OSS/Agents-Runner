from __future__ import annotations

import os

from agents_runner.agent_cli import normalize_agent
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
    def _is_missing_container_error(exc: Exception) -> bool:
        text = str(exc or "").lower()
        if "no such" in text and ("container" in text or "object" in text):
            return True
        if "could not find" in text and "container" in text:
            return True
        return False

    @staticmethod
    def _should_archive_task(task: Task) -> bool:
        status = (task.status or "").lower()
        if status == "discarded":
            return True
        if not (task.is_done() or task.is_failed()):
            return False
        return (str(getattr(task, "finalization_state", "") or "").lower() == "done")

    @staticmethod
    def _try_sync_container_state(task: Task) -> bool:
        # Special handling for interactive v2 tasks
        if task.is_interactive_run() and task.interactive_version == 2:
            return _MainWindowPersistenceMixin._try_sync_interactive_v2_state(task)
        
        container_id = str(task.container_id or "").strip()
        if not container_id:
            return False
        try:
            from agents_runner.docker.process import _inspect_state
        except Exception:
            return False
        try:
            state = _inspect_state(container_id)
        except Exception as exc:
            if _MainWindowPersistenceMixin._is_missing_container_error(exc):
                status = (task.status or "").lower()
                if status not in {"cancelled", "killed"}:
                    task.status = "failed"
                if task.exit_code is None and task.status == "failed":
                    task.exit_code = 1
                if task.finished_at is None:
                    from datetime import timezone
                    from datetime import datetime

                    task.finished_at = datetime.now(tz=timezone.utc)
                detail = str(task.error or "").strip()
                reason = "container missing on restart"
                task.error = f"{detail}; {reason}" if detail else reason
                return True
            return False
        if not isinstance(state, dict) or not state:
            return False

        incoming = str(state.get("Status") or "").strip().lower()
        if incoming and (task.status or "").lower() not in {"cancelled", "killed"}:
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

        status = (task.status or "").lower()
        if (
            status in {"exited", "dead"}
            and task.exit_code is not None
            and (task.status or "").lower() not in {"cancelled", "killed"}
        ):
            task.status = "done" if status == "exited" and task.exit_code == 0 else "failed"
            if task.finished_at is None:
                from datetime import datetime
                from datetime import timezone

                task.finished_at = datetime.now(tz=timezone.utc)
        return True
    
    @staticmethod
    def _try_sync_interactive_v2_state(task: Task) -> bool:
        """Sync interactive v2 task state after restart.
        
        For interactive v2 tasks:
        1. Check for completion marker in staging directory
        2. If marker exists, task is done - read exit code and timestamps
        3. If no marker and container is running, task is still active
        4. If no marker and no container, mark as unknown
        
        Args:
            task: Task object
        
        Returns:
            True if state was synced
        """
        from agents_runner.ui.task_staging import read_interactive_completion_marker
        
        # Check for completion marker first
        marker = read_interactive_completion_marker(task.task_id)
        if marker:
            # Task completed, read from marker
            task.exit_code = int(marker.get("exit_code", 0))
            task.status = "done" if task.exit_code == 0 else "failed"
            
            # Parse timestamps
            finished_at_str = str(marker.get("finished_at", ""))
            try:
                from datetime import datetime
                task.finished_at = datetime.fromisoformat(
                    finished_at_str.replace("Z", "+00:00")
                )
            except Exception:
                from datetime import datetime, timezone
                task.finished_at = datetime.now(tz=timezone.utc)
            
            started_at_str = str(marker.get("started_at", ""))
            try:
                from datetime import datetime
                task.started_at = datetime.fromisoformat(
                    started_at_str.replace("Z", "+00:00")
                )
            except Exception:
                pass
            
            return True
        
        # No completion marker, check if container is running
        container_id = str(task.container_id or "").strip()
        if not container_id:
            # Mark as unknown - no marker and no container ID
            task.status = "unknown"
            task.error = "Interactive task missing completion marker and container ID"
            return True
        
        try:
            from agents_runner.docker.process import _inspect_state
            state = _inspect_state(container_id)
        except Exception as exc:
            if _MainWindowPersistenceMixin._is_missing_container_error(exc):
                # Container is gone but no completion marker
                # This happens if container was manually removed or crashed
                task.status = "unknown"
                task.error = "Interactive task container missing (no completion marker)"
                from datetime import datetime, timezone
                if task.finished_at is None:
                    task.finished_at = datetime.now(tz=timezone.utc)
                return True
            return False
        
        if not isinstance(state, dict) or not state:
            return False
        
        # Container exists, sync state
        incoming = str(state.get("Status") or "").strip().lower()
        if incoming and (task.status or "").lower() not in {"cancelled", "killed"}:
            task.status = incoming
        
        started_at = _parse_docker_time(state.get("StartedAt"))
        if started_at:
            task.started_at = started_at
        
        # If container is running, we're good
        # The docker wait monitor will pick it up when the app fully starts
        return True

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _save_state(self) -> None:
        from agents_runner.persistence import save_watch_state

        payload = {"settings": dict(self._settings_data)}

        # Save watch states
        save_watch_state(payload, self._watch_states)

        save_state(self._state_path, payload)
        for task in sorted(self._tasks.values(), key=lambda t: t.created_at_s):
            save_task_payload(
                self._state_path,
                serialize_task(task),
                archived=self._should_archive_task(task),
            )

    def _load_state(self) -> None:
        from agents_runner.persistence import load_watch_state

        try:
            payload = load_state(self._state_path)
        except Exception:
            return

        # Load watch states
        self._watch_states.update(load_watch_state(payload))

        settings = payload.get("settings")
        if isinstance(settings, dict):
            self._settings_data.update(settings)
        self._settings_data.pop("stt_mode", None)
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
        self._settings_data.setdefault("headless_desktop_enabled", False)
        self._settings_data.setdefault("spellcheck_enabled", True)
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
            synced = False
            status = (task.status or "").lower()
            if status != "queued":
                synced = self._try_sync_container_state(task)
            if self._should_archive_task(task):
                save_task_payload(self._state_path, serialize_task(task), archived=True)
                continue
            status = (task.status or "").lower()
            if not synced and task.is_active() and status != "queued":
                task.status = "unknown"
            loaded.append(task)
        loaded.sort(key=lambda t: t.created_at_s)
        
        # Repair missing git metadata for cloned repo tasks
        repair_count = 0
        for task in loaded:
            if task.requires_git_metadata() and not task.git:
                from agents_runner.ui.task_repair import repair_task_git_metadata
                success, msg = repair_task_git_metadata(
                    task,
                    state_path=self._state_path,
                    environments=self._environments,
                )
                if success:
                    repair_count += 1
                    # Save repaired task immediately
                    save_task_payload(
                        self._state_path,
                        serialize_task(task),
                        archived=self._should_archive_task(task),
                    )
        
        if repair_count > 0:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Repaired git metadata for {repair_count} tasks")
        
        for task in loaded:
            self._tasks[task.task_id] = task
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

        try:
            self._reconcile_tasks_after_restart()
        except Exception:
            pass
