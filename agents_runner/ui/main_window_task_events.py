from __future__ import annotations

import subprocess
import threading
import time

from datetime import datetime
from datetime import timezone

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.log_format import format_log
from agents_runner.log_format import format_log_display
from agents_runner.log_format import prettify_log_line
from agents_runner.persistence import deserialize_task
from agents_runner.persistence import load_task_payload
from agents_runner.persistence import save_task_payload
from agents_runner.persistence import serialize_task
from agents_runner.artifacts import collect_artifacts_from_container_with_timeout
from agents_runner.ui.bridges import TaskRunnerBridge
from agents_runner.ui.task_git_metadata import derive_task_git_metadata
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _parse_docker_time
from agents_runner.ui.utils import _stain_color


class _MainWindowTaskEventsMixin:
    def _open_task_details(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return

        task = self._tasks.get(task_id)
        if task is None:
            payload = load_task_payload(self._state_path, task_id, archived=True)
            if not isinstance(payload, dict):
                return
            task = deserialize_task(Task, payload)
            if task.logs:
                task.logs = [
                    format_log_display(prettify_log_line(line))
                    for line in task.logs
                    if isinstance(line, str)
                ]

        self._details.show_task(task)
        self._show_task_details()

    def _on_task_container_action(self, task_id: str, action: str) -> None:
        task_id = str(task_id or "").strip()
        action = str(action or "").strip().lower()
        task = self._tasks.get(task_id)
        if task is None:
            return

        bridge = self._bridges.get(task_id)
        container_id = task.container_id or (
            bridge.container_id if bridge is not None else None
        )
        container_id = str(container_id or "").strip()
        if not container_id:
            QMessageBox.information(
                self, "No container", "This task does not have a container ID yet."
            )
            return

        if action in {"stop", "kill"}:
            current = (task.status or "").lower()
            if current in {"cancelled", "killed"}:
                return

            is_kill = action == "kill"
            task.status = "killed" if is_kill else "cancelled"
            if task.finished_at is None:
                task.finished_at = datetime.now(tz=timezone.utc)
            task.git = derive_task_git_metadata(task)

            self._on_task_log(
                task_id,
                format_log("host", "action", "INFO", "user_kill requested" if is_kill else "user_cancel requested"),
            )

            watch = self._interactive_watch.get(task_id)
            if watch is not None:
                _, stop = watch
                stop.set()

            if bridge is not None:
                try:
                    if is_kill:
                        bridge.request_user_kill()
                    else:
                        bridge.request_user_cancel()
                except Exception:
                    bridge = None

            if bridge is None:
                docker_args = (
                    ["kill", container_id]
                    if is_kill
                    else ["stop", "-t", "1", container_id]
                )
                self._on_task_log(task_id, format_log("docker", "cmd", "INFO", f"docker {' '.join(docker_args)}"))
                try:
                    completed = subprocess.run(
                        ["docker", *docker_args],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=10.0 if is_kill else 20.0,
                    )
                except Exception as exc:
                    self._on_task_log(task_id, format_log("docker", "cmd", "ERROR", str(exc)))
                    completed = None

                if completed is not None and completed.returncode != 0:
                    detail = (completed.stderr or completed.stdout or "").strip()
                    if detail:
                        self._on_task_log(task_id, format_log("docker", "cmd", "ERROR", detail))

            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()

            task.finalization_state = "pending"
            task.finalization_error = ""
            self._schedule_save()
            self._queue_task_finalization(task_id, reason="user_stop")

            return

        docker_args: list[str]
        timeout_s = 10.0
        if action == "freeze":
            docker_args = ["pause", container_id]
        elif action == "unfreeze":
            docker_args = ["unpause", container_id]
        else:
            return

        self._on_task_log(task_id, format_log("docker", "cmd", "INFO", f"docker {' '.join(docker_args)}"))
        try:
            completed = subprocess.run(
                ["docker", *docker_args],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except Exception as exc:
            self._on_task_log(task_id, format_log("docker", "cmd", "ERROR", str(exc)))
            QMessageBox.warning(self, "Docker command failed", str(exc))
            return

        if completed.returncode != 0:
            detail = (
                completed.stderr or completed.stdout or ""
            ).strip() or f"docker exited {completed.returncode}"
            self._on_task_log(task_id, format_log("docker", "cmd", "ERROR", detail))
            QMessageBox.warning(self, "Docker command failed", detail)

        self._try_sync_container_state(task)
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _on_task_reattach_requested(self, task_id: str) -> None:
        """Handle reattach request for running interactive containers."""
        task_id = str(task_id or "").strip()
        task = self._tasks.get(task_id)
        if task is None:
            QMessageBox.warning(self, "Task not found", "Task not found.")
            return
        
        if not task.is_interactive_run():
            QMessageBox.warning(self, "Not an interactive task", "This task is not interactive.")
            return
        
        container_id = str(task.container_id or "").strip()
        if not container_id:
            QMessageBox.warning(self, "No container", "This task does not have a container ID.")
            return
        
        # Check if container is still running
        status = (task.status or "").lower()
        if status not in {"running", "starting", "created"}:
            QMessageBox.warning(
                self,
                "Container not running",
                f"Container is in '{status}' state, cannot reattach.",
            )
            return
        
        # Get environment and terminal info
        env = self._environments.get(task.environment_id)
        if env is None:
            QMessageBox.warning(self, "Environment not found", "Task environment not found.")
            return
        
        # Get terminal options
        from agents_runner.terminal_apps import detect_terminal_options
        
        options = {opt.terminal_id: opt for opt in detect_terminal_options()}
        # Try to get the last used terminal or default to the first available
        terminal_id = getattr(self._settings_data, "terminal_id", None)
        if not terminal_id or terminal_id not in options:
            if options:
                terminal_id = list(options.keys())[0]
        
        terminal_opt = options.get(terminal_id) if terminal_id else None
        if terminal_opt is None:
            QMessageBox.warning(
                self,
                "No terminal available",
                "No terminal emulator found to reattach.",
            )
            return
        
        # Launch terminal with attach mode
        self._launch_reattach_terminal(task, env, terminal_opt)

    def _launch_reattach_terminal(self, task: Task, env: object, terminal_opt: object) -> None:
        """Launch terminal and attach to running container."""
        from agents_runner.ui.shell_templates import shell_log_statement
        from agents_runner.terminal_apps import launch_in_terminal
        from pathlib import Path
        import tempfile
        import shlex
        
        task_id = str(task.task_id or "")
        container_name = str(task.container_id or "")
        
        # Build host shell script in reattach mode
        from agents_runner.ui.main_window_tasks_interactive_docker import (
            _build_host_shell_script,
        )
        
        host_script_content = _build_host_shell_script(
            container_name=container_name,
            task_token=f"reattach-{task_id}",
            tmp_paths={},
            gh_token_snippet="",
            rosetta_snippet="",
            gh_clone_snippet="",
            attach_mode=True,
        )
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, prefix=f"agents-runner-reattach-{task_id}-"
        ) as temp:
            temp.write(host_script_content)
            temp_script_path = temp.name
        
        # Make executable
        import os
        import stat
        
        st = os.stat(temp_script_path)
        os.chmod(temp_script_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        
        # Log reattach action
        self._on_task_log(
            task_id,
            format_log("host", "reattach", "INFO", f"reattaching to container {container_name}"),
        )
        
        # Launch terminal
        try:
            launch_in_terminal(
                terminal_opt=terminal_opt,
                script_path=temp_script_path,
                title=f"Task {task_id} (reattach)",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Failed to launch terminal",
                f"Failed to launch terminal: {exc}",
            )
            return
        
        # Start watching for completion again
        self._start_interactive_finish_watch(task_id)

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
        if (
            QMessageBox.question(self, "Discard task?", message)
            != QMessageBox.StandardButton.Yes
        ):
            return

        task.status = "discarded"
        if task.finished_at is None:
            task.finished_at = datetime.now(tz=timezone.utc)
        task.git = derive_task_git_metadata(task)
        save_task_payload(self._state_path, serialize_task(task), archived=True)

        bridge = self._bridges.get(task_id)
        thread = self._threads.get(task_id)
        container_id = task.container_id or (
            bridge.container_id if bridge is not None else None
        )
        watch = self._interactive_watch.get(task_id)
        if watch is not None:
            _, stop = watch
            stop.set()

        if bridge is not None:
            try:
                bridge.request_user_cancel()
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

        # Clean up task workspace (if using cloned GitHub repo)
        if task.workspace_type == WORKSPACE_CLONED and task.environment_id:
            threading.Thread(
                target=self._cleanup_task_workspace_async,
                args=(task_id, task.environment_id),
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

    def _cleanup_task_workspace_async(self, task_id: str, env_id: str) -> None:
        """Clean up task workspace in background thread."""
        import os

        data_dir = os.path.dirname(self._state_path)
        cleanup_task_workspace(
            env_id=env_id,
            task_id=task_id,
            data_dir=data_dir,
            on_log=None,  # Silent cleanup (no UI updates)
        )

    def _on_bridge_state(self, task_id: str, state: dict) -> None:
        self._on_task_state(task_id, state)

    def _on_bridge_log(self, task_id: str, line: str) -> None:
        self._on_task_log(task_id, line)

    def _on_bridge_retry_attempt(
        self, task_id: str, attempt_number: int, agent: str, delay: float
    ) -> None:
        """Handle retry attempt signal from supervisor."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        if (task.status or "").lower() in {"cancelled", "killed"}:
            return

        self._on_task_log(
            task_id,
            format_log("supervisor", "retry", "INFO", f"starting attempt {attempt_number} with {agent} (fallback)"),
        )
        task.status = f"retrying (attempt {attempt_number})"
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _on_bridge_agent_switched(self, task_id: str, from_agent: str, to_agent: str) -> None:
        """Handle agent switch signal from supervisor."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        if (task.status or "").lower() in {"cancelled", "killed"}:
            return

        self._on_task_log(
            task_id,
            format_log("supervisor", "fallback", "INFO", f"switching from {from_agent} to {to_agent} (fallback)"),
        )
        task.agent_cli = to_agent
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _on_bridge_done(
        self, task_id: str, exit_code: int, error: object, artifacts: list, metadata: dict | None = None
    ) -> None:
        bridge = self._bridges.get(task_id)
        task = self._tasks.get(task_id)
        if task is None:
            return

        # Capture GitHub repo info from the worker if available
        if isinstance(bridge, TaskRunnerBridge):
            try:
                if bridge.gh_repo_root:
                    task.gh_repo_root = bridge.gh_repo_root
                if bridge.gh_base_branch and not task.gh_base_branch:
                    task.gh_base_branch = bridge.gh_base_branch
                if bridge.gh_branch:
                    task.gh_branch = bridge.gh_branch
            except Exception:
                # Best-effort: bridge may already be deleted on its thread.
                pass

        # Store collected artifacts
        if artifacts:
            task.artifacts = list(artifacts)

        # Capture metadata from supervisor
        if metadata:
            agent_used = metadata.get("agent_used")
            agent_id = metadata.get("agent_id")
            retry_count = metadata.get("retry_count", 0)
            attempt_history = metadata.get("attempt_history")

            if agent_used:
                task.agent_cli = agent_used
            if agent_id:
                task.agent_instance_id = agent_id
            if isinstance(attempt_history, list):
                task.attempt_history = attempt_history

            if retry_count > 0:
                self._on_task_log(
                    task_id,
                    format_log("supervisor", "retry", "INFO", f"completed after {retry_count} retries"),
                )

        self._on_task_done(task_id, exit_code, error, metadata=metadata)

    def _on_host_log(self, task_id: str, line: str) -> None:
        self._on_task_log(task_id, line)

    def _on_host_pr_url(self, task_id: str, pr_url: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.gh_pr_url = str(pr_url or "").strip()
        task.git = derive_task_git_metadata(task)
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _on_host_artifacts(self, task_id: str, artifacts: object) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        if not isinstance(artifacts, list):
            return
        artifact_uuids = [str(item) for item in artifacts if str(item).strip()]
        if not artifact_uuids:
            return
        task.artifacts = artifact_uuids
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
        task.logs.append(cleaned)  # Store raw canonical format
        if len(task.logs) > 6000:
            task.logs = task.logs[-5000:]
        display_line = format_log_display(cleaned)  # Format for display
        self._details.append_log(task_id, display_line)
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
        if current in {"cancelled", "killed"}:
            if bridge and bridge.container_id:
                task.container_id = bridge.container_id
            finished_at = _parse_docker_time(state.get("FinishedAt"))
            if finished_at and task.finished_at is None:
                task.finished_at = finished_at
            exit_code = state.get("ExitCode")
            if exit_code is not None:
                try:
                    task.exit_code = int(exit_code)
                except Exception:
                    pass
            self._details.update_task(task)
            self._schedule_save()
            return

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

        if "DesktopEnabled" in state:
            task.headless_desktop_enabled = bool(state.get("DesktopEnabled") or False)
            task.vnc_password = ""
        novnc_url = str(state.get("NoVncUrl") or "").strip()
        if novnc_url:
            task.novnc_url = novnc_url
        desktop_display = str(state.get("DesktopDisplay") or "").strip()
        if desktop_display:
            task.desktop_display = desktop_display

        if current not in {"done", "failed"}:
            if incoming in {"exited", "dead"} and task.exit_code is not None:
                task.status = (
                    "done"
                    if (incoming == "exited" and task.exit_code == 0)
                    else "failed"
                )
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

    def _on_task_done(
        self, task_id: str, exit_code: int, error: object, *, metadata: dict | None = None
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        try:
            self._on_task_log(
                task_id, format_log("host", "finalize", "INFO", "finalization queued")
            )

            if task.started_at is None:
                started_s = self._run_started_s.get(task_id)
                if started_s is not None:
                    task.started_at = datetime.fromtimestamp(started_s, tz=timezone.utc)
            if task.finished_at is None:
                task.finished_at = datetime.now(tz=timezone.utc)

            user_stop = None
            status_lower = (task.status or "").lower()
            if status_lower in {"cancelled", "killed"}:
                user_stop = "kill" if status_lower == "killed" else "cancel"
            elif metadata:
                candidate = str(metadata.get("user_stop") or "").strip().lower()
                if candidate in {"cancel", "kill"}:
                    user_stop = candidate
                    task.status = "killed" if candidate == "kill" else "cancelled"

            task.exit_code = int(exit_code)
            if user_stop is not None:
                task.error = None
            elif error:
                task.status = "failed"
                task.error = str(error)
            else:
                task.status = "done" if int(exit_code) == 0 else "failed"

            task.git = derive_task_git_metadata(task)

            # Validate git metadata for cloned repo tasks
            if task.requires_git_metadata():
                from agents_runner.ui.task_git_metadata import validate_git_metadata
                is_valid, error_msg = validate_git_metadata(task.git)
                if not is_valid:
                    self._on_task_log(
                        task_id,
                        format_log("host", "metadata", "WARN", 
                                   f"git metadata validation failed: {error_msg}")
                    )
                    # Note: We don't fail the task itself, as the code execution may have succeeded
                    # The metadata issue will be flagged but won't affect task completion status

            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            if user_stop is None:
                QApplication.beep()

            self._on_task_log(
                task_id,
                format_log("host", "finalize", "INFO", f"task marked complete: status={task.status} exit_code={task.exit_code}"),
            )
            self._try_start_queued_tasks()

            task.finalization_state = "pending"
            task.finalization_error = ""
            self._schedule_save()
            self._queue_task_finalization(task_id, reason="task_done")
        finally:
            pass

    def _cleanup_cloned_repo_workspace_async(self, task_id: str, env_id: str) -> None:
        """Clean up cloned repo workspace for a task asynchronously.
        
        This is used when PR creation is skipped (otherwise the PR worker
        performs cleanup after finishing).
        """
        import os
        try:
            state_path = getattr(self, "_state_path", "")
            if not state_path:
                self._on_task_log(
                    task_id,
                    format_log("gh", "cleanup", "WARN", "cleanup skipped: state path not available")
                )
                return
            
            self._on_task_log(task_id, format_log("gh", "cleanup", "INFO", "cleaning up task workspace"))
            data_dir = os.path.dirname(state_path)
            cleanup_success = cleanup_task_workspace(
                env_id=env_id,
                task_id=task_id,
                data_dir=data_dir,
                on_log=lambda msg: self._on_task_log(task_id, msg),
            )
            if cleanup_success:
                self._on_task_log(task_id, format_log("gh", "cleanup", "INFO", "task workspace cleaned"))
        except Exception as cleanup_exc:
            self._on_task_log(
                task_id,
                format_log("gh", "cleanup", "ERROR", f"cleanup failed: {cleanup_exc}")
            )

    def _start_artifact_finalization(self, task: Task) -> None:
        if getattr(task, "_artifact_finalization_started", False):
            return
        try:
            setattr(task, "_artifact_finalization_started", True)
        except Exception:
            pass

        runner_config = getattr(task, "_runner_config", None)
        timeout_s = 30.0
        if runner_config is not None:
            try:
                timeout_s = float(getattr(runner_config, "artifact_collection_timeout_s"))
            except Exception:
                timeout_s = 30.0
        if timeout_s <= 0.0:
            timeout_s = 30.0

        container_id = str(task.container_id or "")
        env_name = str(task.environment_id or "")
        task_dict = {
            "task_id": str(task.task_id or ""),
            "image": str(task.image or ""),
            "agent_cli": str(task.agent_cli or ""),
            "created_at": float(task.created_at_s or 0.0),
        }

        def _worker() -> None:
            start = time.monotonic()
            self.host_log.emit(task.task_id, format_log("host", "artifacts", "INFO", "collecting artifacts from container..."))
            try:
                artifact_uuids = collect_artifacts_from_container_with_timeout(
                    container_id,
                    task_dict,
                    env_name,
                    timeout_s=timeout_s,
                )
                elapsed_s = time.monotonic() - start
                self.host_log.emit(
                    task.task_id,
                    format_log("host", "finalize", "INFO", f"artifact collection finished in {elapsed_s:.1f}s ({len(artifact_uuids)} artifact(s))"),
                )
                if artifact_uuids:
                    self.host_artifacts.emit(task.task_id, artifact_uuids)
            except Exception as exc:
                elapsed_s = time.monotonic() - start
                self.host_log.emit(
                    task.task_id,
                    format_log("host", "artifacts", "ERROR", f"artifact collection failed/timeout: {exc} (elapsed {elapsed_s:.1f}s)"),
                )

        threading.Thread(target=_worker, daemon=True).start()
