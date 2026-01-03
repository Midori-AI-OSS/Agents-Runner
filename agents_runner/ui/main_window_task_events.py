from __future__ import annotations

import os
import subprocess
import threading
import time

from datetime import datetime
from datetime import timezone

from PySide6.QtCore import QMetaObject
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import GH_MANAGEMENT_NONE
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.log_format import prettify_log_line
from agents_runner.persistence import save_task_payload
from agents_runner.persistence import serialize_task
from agents_runner.ui.bridges import TaskRunnerBridge
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _parse_docker_time
from agents_runner.ui.utils import _stain_color


class _MainWindowTaskEventsMixin:
    def _open_task_details(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        self._details.show_task(task)
        self._show_task_details()


    def _discard_task_from_ui(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        task = self._tasks.get(task_id)
        if task is None:
            return

        prompt = task.prompt_one_line()
        message = (
            f"Discard task {task_id}?\n\n"
            f"{prompt}\n\n"
            "This removes it from the list, archives it for auditing, and will attempt to stop/remove any running container."
        )
        if QMessageBox.question(self, "Discard task?", message) != QMessageBox.StandardButton.Yes:
            return

        task.status = "discarded"
        if task.finished_at is None:
            task.finished_at = datetime.now(tz=timezone.utc)
        save_task_payload(self._state_path, serialize_task(task), archived=True)

        bridge = self._bridges.get(task_id)
        thread = self._threads.get(task_id)
        container_id = task.container_id or (bridge.container_id if bridge is not None else None)
        watch = self._interactive_watch.get(task_id)
        if watch is not None:
            _, stop = watch
            stop.set()

        if bridge is not None:
            try:
                QMetaObject.invokeMethod(bridge, "request_stop", Qt.QueuedConnection)
            except Exception:
                pass
        if thread is not None:
            try:
                thread.quit()
            except Exception:
                pass

        self._dashboard.remove_tasks({task_id})
        self._tasks.pop(task_id, None)
        self._threads.pop(task_id, None)
        self._bridges.pop(task_id, None)
        self._run_started_s.pop(task_id, None)
        self._dashboard_log_refresh_s.pop(task_id, None)
        self._interactive_watch.pop(task_id, None)
        self._schedule_save()

        if self._details.isVisible() and self._details.current_task_id() == task_id:
            self._show_dashboard()

        if container_id:
            threading.Thread(
                target=self._force_remove_container,
                args=(container_id,),
                daemon=True,
            ).start()


    def _force_remove_container(self, container_id: str) -> None:
        container_id = str(container_id or "").strip()
        if not container_id:
            return
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=25.0,
            )
        except Exception:
            pass


    def _on_bridge_state(self, state: dict) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_state(bridge.task_id, state)


    def _on_bridge_log(self, line: str) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_log(bridge.task_id, line)


    def _on_bridge_done(self, exit_code: int, error: object) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            # Capture GitHub repo info from the worker if available
            task = self._tasks.get(bridge.task_id)
            if task is not None:
                if bridge.gh_repo_root:
                    task.gh_repo_root = bridge.gh_repo_root
                if bridge.gh_base_branch:
                    task.gh_base_branch = bridge.gh_base_branch
                if bridge.gh_branch:
                    task.gh_branch = bridge.gh_branch
            self._on_task_done(bridge.task_id, exit_code, error)


    def _on_host_log(self, task_id: str, line: str) -> None:
        self._on_task_log(task_id, line)


    def _on_host_pr_url(self, task_id: str, pr_url: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.gh_pr_url = str(pr_url or "").strip()
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()


    def _on_task_log(self, task_id: str, line: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        cleaned = prettify_log_line(line)
        task.logs.append(cleaned)
        if len(task.logs) > 6000:
            task.logs = task.logs[-5000:]
        self._details.append_log(task_id, cleaned)
        self._schedule_save()
        if cleaned and self._dashboard.isVisible() and task.is_active():
            now_s = time.time()
            last_s = float(self._dashboard_log_refresh_s.get(task_id) or 0.0)
            if now_s - last_s >= 0.25:
                self._dashboard_log_refresh_s[task_id] = now_s
                env = self._environments.get(task.environment_id)
                stain = env.color if env else None
                spinner = _stain_color(env.color) if env else None
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        if "docker pull" in cleaned and (task.status or "").lower() != "pulling":
            task.status = "pulling"
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._schedule_save()


    def _on_task_state(self, task_id: str, state: dict) -> None:
        task = self._tasks.get(task_id)
        bridge = self._bridges.get(task_id)
        if task is None:
            return

        current = (task.status or "").lower()
        incoming = str(state.get("Status") or task.status or "—").lower()
        if bridge and bridge.container_id:
            task.container_id = bridge.container_id

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

        if current not in {"done", "failed"}:
            if incoming in {"exited", "dead"} and task.exit_code is not None:
                task.status = "done" if (incoming == "exited" and task.exit_code == 0) else "failed"
                if task.finished_at is None:
                    task.finished_at = datetime.now(tz=timezone.utc)
                self._try_start_queued_tasks()
            else:
                task.status = incoming

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()


    def _on_task_done(self, task_id: str, exit_code: int, error: object) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return

        if task.started_at is None:
            started_s = self._run_started_s.get(task_id)
            if started_s is not None:
                task.started_at = datetime.fromtimestamp(started_s, tz=timezone.utc)
        if task.finished_at is None:
            task.finished_at = datetime.now(tz=timezone.utc)

        if error:
            task.status = "failed"
            task.error = str(error)
        else:
            task.exit_code = int(exit_code)
            task.status = "done" if int(exit_code) == 0 else "failed"

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()
        QApplication.beep()

        self._try_start_queued_tasks()

        if (
            normalize_gh_management_mode(task.gh_management_mode) != GH_MANAGEMENT_NONE
            and task.gh_repo_root
            and task.gh_branch
        ):
            repo_root = str(task.gh_repo_root or "").strip()
            branch = str(task.gh_branch or "").strip()
            base_branch = str(task.gh_base_branch or "").strip() or "main"
            prompt_text = str(task.prompt or "")
            task_token = str(task.task_id or task_id)
            pr_metadata_path = str(task.gh_pr_metadata_path or "").strip() or None
            threading.Thread(
                target=self._finalize_gh_management_worker,
                args=(
                    task_id,
                    repo_root,
                    branch,
                    base_branch,
                    prompt_text,
                    task_token,
                    bool(task.gh_use_host_cli),
                    pr_metadata_path,
                    str(task.agent_cli or "").strip(),
                    str(task.agent_cli_args or "").strip(),
                ),
                daemon=True,
            ).start()
