from __future__ import annotations

import subprocess
import threading
import time

from datetime import datetime
from datetime import timezone

from PySide6.QtCore import QMetaObject
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import GH_MANAGEMENT_NONE
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
                    QMetaObject.invokeMethod(
                        bridge,
                        "request_user_kill" if is_kill else "request_user_cancel",
                        Qt.DirectConnection,
                    )
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

            # Task.gh_management_mode already contains normalized values
            if task.gh_management_mode == GH_MANAGEMENT_GITHUB and task.environment_id:
                threading.Thread(
                    target=self._cleanup_task_workspace_async,
                    args=(task_id, task.environment_id),
                    daemon=True,
                ).start()

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
                QMetaObject.invokeMethod(
                    bridge, "request_user_cancel", Qt.DirectConnection
                )
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

        # Clean up task workspace (if using GitHub management)
        # Task.gh_management_mode already contains normalized values
        if task.gh_management_mode == GH_MANAGEMENT_GITHUB and task.environment_id:
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

    def _on_bridge_state(self, state: dict) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_state(bridge.task_id, state)

    def _on_bridge_log(self, line: str) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_log(bridge.task_id, line)

    def _on_bridge_retry_attempt(
        self, attempt_number: int, agent: str, delay: float
    ) -> None:
        """Handle retry attempt signal from supervisor."""
        bridge = self.sender()
        if not isinstance(bridge, TaskRunnerBridge):
            return

        task = self._tasks.get(bridge.task_id)
        if task is None:
            return
        if (task.status or "").lower() in {"cancelled", "killed"}:
            return

        self._on_task_log(
            bridge.task_id,
            format_log("supervisor", "retry", "INFO", f"starting attempt {attempt_number} with {agent} (fallback)"),
        )
        task.status = f"retrying (attempt {attempt_number})"
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _on_bridge_agent_switched(self, from_agent: str, to_agent: str) -> None:
        """Handle agent switch signal from supervisor."""
        bridge = self.sender()
        if not isinstance(bridge, TaskRunnerBridge):
            return

        task = self._tasks.get(bridge.task_id)
        if task is None:
            return
        if (task.status or "").lower() in {"cancelled", "killed"}:
            return

        self._on_task_log(
            bridge.task_id,
            format_log("supervisor", "fallback", "INFO", f"switching from {from_agent} to {to_agent} (fallback)"),
        )
        task.agent_cli = to_agent
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _on_bridge_done(
        self, exit_code: int, error: object, artifacts: list, metadata: dict | None = None
    ) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            # Capture GitHub repo info from the worker if available
            task = self._tasks.get(bridge.task_id)
            if task is not None:
                if bridge.gh_repo_root:
                    task.gh_repo_root = bridge.gh_repo_root
                if bridge.gh_base_branch and not task.gh_base_branch:
                    task.gh_base_branch = bridge.gh_base_branch
                if bridge.gh_branch:
                    task.gh_branch = bridge.gh_branch
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
                            bridge.task_id,
                            format_log("supervisor", "retry", "INFO", f"completed after {retry_count} retries"),
                        )
            self._on_task_done(bridge.task_id, exit_code, error, metadata=metadata)

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
        pr_worker_started = False

        try:
            self._on_task_log(task_id, format_log("host", "finalize", "INFO", "finalization started"))

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

            # Validate git metadata for git-locked tasks
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
            if user_stop is None:
                self._start_artifact_finalization(task)

            self._try_start_queued_tasks()

            # Determine if PR should be created and log skip reason if not
            should_create_pr = False
            skip_reason = None

            if user_stop is not None:
                skip_reason = f"user stopped task ({user_stop})"
            elif task.gh_management_mode != GH_MANAGEMENT_GITHUB:
                skip_reason = f"not a GitHub-managed environment (mode={task.gh_management_mode})"
            elif not task.gh_repo_root:
                skip_reason = "missing repository root information"
            elif not task.gh_branch:
                skip_reason = "missing branch information"
            elif task.gh_pr_url:
                skip_reason = "PR already created"
            else:
                should_create_pr = True

            if should_create_pr:
                repo_root = str(task.gh_repo_root or "").strip()
                branch = str(task.gh_branch or "").strip()
                base_branch = str(task.gh_base_branch or "").strip()
                prompt_text = str(task.prompt or "")
                task_token = str(task.task_id or task_id)
                pr_metadata_path = str(task.gh_pr_metadata_path or "").strip() or None
                pr_worker_started = True
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
            else:
                self._on_task_log(task_id, format_log("gh", "pr", "INFO", f"PR creation skipped: {skip_reason}"))
        finally:
            # Cleanup must not race PR creation/validation: when a PR worker is started,
            # it owns cleanup after finishing (success or failure).
            if (
                not pr_worker_started
                and task.gh_management_mode == GH_MANAGEMENT_GITHUB
                and task.environment_id
                and task_id
            ):
                threading.Thread(
                    target=self._cleanup_git_locked_workspace_async,
                    args=(task_id, task.environment_id),
                    daemon=True,
                ).start()

    def _cleanup_git_locked_workspace_async(self, task_id: str, env_id: str) -> None:
        """Clean up git-locked workspace for a task asynchronously.
        
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
