from __future__ import annotations

import subprocess
import threading
import time

from datetime import datetime
from datetime import timezone
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import save_environment
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
from agents_runner.ui.task_event_proxy import BufferedTaskEvent
from agents_runner.ui.task_event_proxy import TaskEventProxy
from agents_runner.ui.task_git_metadata import derive_task_git_metadata
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import parse_docker_time
from agents_runner.ui.utils import stain_color


class MainWindowTaskEventsMixin:
    _IDE_NOVNC_AUTO_OPEN_DELAY_S = 15.0

    def _stop_ide_novnc_auto_open_timer(self, task_id: str) -> None:
        timer = self._ide_novnc_auto_open_timers.pop(task_id, None)
        if timer is None:
            return
        try:
            timer.stop()
            timer.deleteLater()
        except Exception:
            pass

    def _clear_ide_novnc_auto_open_state(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        self._stop_ide_novnc_auto_open_timer(task_id)
        self._ide_novnc_auto_open_urls.pop(task_id, None)
        self._ide_novnc_auto_open_ready_s.pop(task_id, None)
        self._ide_novnc_auto_open_deferred.discard(task_id)
        self._ide_novnc_auto_opened_tasks.discard(task_id)

    def _is_task_viewed_in_details(self, task_id: str) -> bool:
        task_id = str(task_id or "").strip()
        if not task_id:
            return False
        try:
            if not bool(self._details.isVisible()):
                return False
        except Exception:
            return False
        try:
            return str(self._details.current_task_id() or "").strip() == task_id
        except Exception:
            return False

    def _is_ide_container_task(self, task: Task) -> bool:
        launch_mode = str(getattr(task, "launch_mode", "") or "").strip().lower()
        if launch_mode != "ide":
            return False
        if str(getattr(task, "novnc_url", "") or "").strip():
            return True
        return bool(getattr(task, "headless_desktop_enabled", False))

    def _schedule_ide_novnc_auto_open_timer(
        self, *, task_id: str, delay_ms: int
    ) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        existing = self._ide_novnc_auto_open_timers.get(task_id)
        if existing is not None:
            try:
                existing.stop()
                existing.deleteLater()
            except Exception:
                pass
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda task_id=task_id: self._on_ide_novnc_auto_open_timeout(task_id)
        )
        timer.start(max(0, int(delay_ms)))
        self._ide_novnc_auto_open_timers[task_id] = timer

    def _maybe_schedule_ide_novnc_auto_open(self, task: Task) -> None:
        task_id = str(getattr(task, "task_id", "") or "").strip()
        if not task_id:
            return
        if task_id in self._ide_novnc_auto_opened_tasks:
            self._stop_ide_novnc_auto_open_timer(task_id)
            return
        if not self._ide_novnc_auto_open_enabled():
            self._clear_ide_novnc_auto_open_state(task_id)
            return
        if not self._is_ide_container_task(task):
            self._clear_ide_novnc_auto_open_state(task_id)
            return
        if not task.is_active():
            self._clear_ide_novnc_auto_open_state(task_id)
            return

        novnc_url = str(getattr(task, "novnc_url", "") or "").strip()
        if not novnc_url:
            self._stop_ide_novnc_auto_open_timer(task_id)
            return

        ready_since = self._ide_novnc_auto_open_ready_s.get(task_id)
        if ready_since is None:
            ready_since = time.time()
            self._ide_novnc_auto_open_ready_s[task_id] = ready_since
        self._ide_novnc_auto_open_urls[task_id] = novnc_url

        mode = self._ide_novnc_auto_open_mode()
        if mode == "viewing_only" and not self._is_task_viewed_in_details(task_id):
            self._ide_novnc_auto_open_deferred.add(task_id)
            self._stop_ide_novnc_auto_open_timer(task_id)
            return

        self._ide_novnc_auto_open_deferred.discard(task_id)
        elapsed_s = max(0.0, time.time() - ready_since)
        remaining_s = max(0.0, self._IDE_NOVNC_AUTO_OPEN_DELAY_S - elapsed_s)
        self._schedule_ide_novnc_auto_open_timer(
            task_id=task_id, delay_ms=int(round(remaining_s * 1000))
        )

    def _on_ide_novnc_auto_open_timeout(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        self._stop_ide_novnc_auto_open_timer(task_id)
        task = self._tasks.get(task_id)
        if task is None:
            self._clear_ide_novnc_auto_open_state(task_id)
            return
        if not self._ide_novnc_auto_open_enabled():
            self._clear_ide_novnc_auto_open_state(task_id)
            return
        if not self._is_ide_container_task(task) or not task.is_active():
            self._clear_ide_novnc_auto_open_state(task_id)
            return

        novnc_url = str(
            task.novnc_url or self._ide_novnc_auto_open_urls.get(task_id) or ""
        )
        novnc_url = novnc_url.strip()
        if not novnc_url:
            return

        mode = self._ide_novnc_auto_open_mode()
        if mode == "viewing_only" and not self._is_task_viewed_in_details(task_id):
            self._ide_novnc_auto_open_deferred.add(task_id)
            return

        launched = self._details.launch_desktop_viewer_for_task(
            task_id=task_id,
            url=novnc_url,
        )
        if launched:
            self._ide_novnc_auto_opened_tasks.add(task_id)
            self._ide_novnc_auto_open_deferred.discard(task_id)

    def _on_task_viewed_for_ide_novnc_auto_open(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        if task_id not in self._ide_novnc_auto_open_deferred:
            return
        task = self._tasks.get(task_id)
        if task is None:
            self._clear_ide_novnc_auto_open_state(task_id)
            return
        self._maybe_schedule_ide_novnc_auto_open(task)

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
        self._on_task_viewed_for_ide_novnc_auto_open(task_id)

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
                format_log(
                    "host",
                    "action",
                    "INFO",
                    "user_kill requested" if is_kill else "user_cancel requested",
                ),
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
                self._on_task_log(
                    task_id,
                    format_log(
                        "docker", "cmd", "INFO", f"docker {' '.join(docker_args)}"
                    ),
                )
                try:
                    completed = subprocess.run(
                        ["docker", *docker_args],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=10.0 if is_kill else 20.0,
                    )
                except Exception as exc:
                    self._on_task_log(
                        task_id, format_log("docker", "cmd", "ERROR", str(exc))
                    )
                    completed = None

                if completed is not None and completed.returncode != 0:
                    detail = (completed.stderr or completed.stdout or "").strip()
                    if detail:
                        self._on_task_log(
                            task_id, format_log("docker", "cmd", "ERROR", detail)
                        )

            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            self._refresh_new_task_agent_info()

            # SYNCHRONIZATION: Set finalization_state to "pending" BEFORE calling _queue_task_finalization().
            # This atomic state transition ensures recovery_tick sees the state change and avoids
            # duplicate finalization work. Same pattern as task_done path for consistency.
            task.finalization_state = "pending"
            task.finalization_error = ""
            self._schedule_save()
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"Task {task_id}: queueing finalization (reason=user_stop, state={task.status})",
                ),
            )
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

        self._on_task_log(
            task_id,
            format_log("docker", "cmd", "INFO", f"docker {' '.join(docker_args)}"),
        )
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
        spinner = stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _discard_task_from_ui(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        task = self._tasks.get(task_id)
        if task is None:
            return
        self._clear_ide_novnc_auto_open_state(task_id)

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
        prep_workers = getattr(self, "_interactive_prep_workers", {})
        prep_threads = getattr(self, "_interactive_prep_threads", {})
        prep_bridges = getattr(self, "_interactive_prep_bridges", {})
        prep_context = getattr(self, "_interactive_prep_context", {})
        prep_worker = prep_workers.get(task_id)
        prep_thread = prep_threads.get(task_id)
        prep_bridge = prep_bridges.get(task_id)
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
        if prep_worker is not None:
            try:
                prep_worker.request_stop()
            except Exception:
                pass
        if thread is not None:
            try:
                thread.quit()
            except Exception:
                pass
        if prep_thread is not None:
            try:
                prep_thread.quit()
                prep_thread.wait(200)
            except Exception:
                pass
        if prep_bridge is not None:
            try:
                prep_bridge.deleteLater()
            except Exception:
                pass

        self._dashboard.remove_tasks({task_id})
        self._tasks.pop(task_id, None)
        self._threads.pop(task_id, None)
        self._bridges.pop(task_id, None)
        prep_threads.pop(task_id, None)
        prep_workers.pop(task_id, None)
        prep_bridges.pop(task_id, None)
        prep_context.pop(task_id, None)
        self._run_started_s.pop(task_id, None)
        self._dashboard_log_refresh_s.pop(task_id, None)
        self._interactive_watch.pop(task_id, None)
        self._remove_task_event_proxy(task_id)
        self._schedule_save()
        self._refresh_new_task_agent_info()

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

    def _ensure_task_event_proxy(self, task_id: str) -> TaskEventProxy:
        task_id = str(task_id or "").strip()
        if not task_id:
            raise ValueError("task_id is required")
        proxies = getattr(self, "_task_event_proxies", {})
        proxy = proxies.get(task_id)
        if proxy is None:
            proxy = TaskEventProxy(task_id=task_id)
            proxies[task_id] = proxy
            self._task_event_proxies = proxies
        timer = getattr(self, "_task_event_drain_timer", None)
        if timer is not None and not timer.isActive():
            timer.start()
        return proxy

    def _remove_task_event_proxy(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        proxies = getattr(self, "_task_event_proxies", {})
        proxy = proxies.pop(task_id, None)
        if proxy is not None:
            proxy.clear()
        timer = getattr(self, "_task_event_drain_timer", None)
        if timer is not None and timer.isActive() and not proxies:
            timer.stop()

    def _connect_task_bridge_events(
        self,
        *,
        task_id: str,
        bridge: TaskRunnerBridge,
        include_supervisor_events: bool,
    ) -> None:
        proxy = self._ensure_task_event_proxy(task_id)
        bridge.state.connect(proxy.enqueue_state, Qt.DirectConnection)
        bridge.log.connect(proxy.enqueue_log, Qt.DirectConnection)
        bridge.done.connect(proxy.enqueue_done, Qt.DirectConnection)
        if include_supervisor_events:
            bridge.retry_attempt.connect(proxy.enqueue_retry, Qt.DirectConnection)
            bridge.agent_switched.connect(
                proxy.enqueue_agent_switched, Qt.DirectConnection
            )

    def _drain_task_event_proxies(self) -> None:
        proxies = getattr(self, "_task_event_proxies", {})
        if not proxies:
            timer = getattr(self, "_task_event_drain_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
            return

        for task_id, proxy in list(proxies.items()):
            events = proxy.drain(max_events=600)
            if not events:
                continue
            self._dispatch_buffered_task_events(
                task_id=task_id, proxy=proxy, events=events
            )
            if proxy.releasable():
                self._remove_task_event_proxy(task_id)

    def _dispatch_buffered_task_events(
        self,
        *,
        task_id: str,
        proxy: TaskEventProxy,
        events: list[BufferedTaskEvent],
    ) -> None:
        if not events:
            return

        state_events: list[dict[str, Any]] = []
        misc_events: list[BufferedTaskEvent] = []
        done_event: BufferedTaskEvent | None = None

        for event in events:
            if event.kind == "state":
                payload = event.payload if isinstance(event.payload, dict) else {}
                state_events.append(dict(payload))
                continue
            if event.kind == "done" and done_event is None:
                done_event = event
                continue
            misc_events.append(event)

        for state in state_events:
            self._on_task_state(task_id, state)

        for event in misc_events:
            if event.kind in {"log", "host_log"}:
                self._on_task_log(task_id, str(event.payload or ""))
                continue
            if event.kind == "retry":
                payload = event.payload
                if isinstance(payload, tuple) and len(payload) == 3:
                    attempt_number, agent, delay = payload
                    self._on_bridge_retry_attempt(
                        task_id,
                        int(attempt_number),
                        str(agent),
                        float(delay),
                    )
                continue
            if event.kind == "agent_switched":
                payload = event.payload
                if isinstance(payload, tuple) and len(payload) == 2:
                    from_agent, to_agent = payload
                    self._on_bridge_agent_switched(
                        task_id,
                        str(from_agent),
                        str(to_agent),
                    )

        if done_event is None:
            return

        done_payload = done_event.payload
        if not isinstance(done_payload, tuple) or len(done_payload) != 4:
            return
        exit_code, error, artifacts, metadata = done_payload
        self._on_bridge_done(
            task_id,
            int(exit_code),
            error,
            list(artifacts or []),
            dict(metadata or {}),
        )
        proxy.mark_bridge_done_dispatched()

    def _on_bridge_state(self, task_id: str, state: dict[str, Any]) -> None:
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
            format_log(
                "supervisor",
                "retry",
                "INFO",
                f"starting attempt {attempt_number} with {agent} (fallback)",
            ),
        )
        task.status = f"retrying (attempt {attempt_number})"
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _on_bridge_agent_switched(
        self, task_id: str, from_agent: str, to_agent: str
    ) -> None:
        """Handle agent switch signal from supervisor."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        if (task.status or "").lower() in {"cancelled", "killed"}:
            return

        self._on_task_log(
            task_id,
            format_log(
                "supervisor",
                "fallback",
                "INFO",
                f"switching from {from_agent} to {to_agent} (fallback)",
            ),
        )
        task.agent_cli = to_agent
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _on_bridge_done(
        self,
        task_id: str,
        exit_code: int,
        error: object,
        artifacts: list[Any],
        metadata: dict[str, Any] | None = None,
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
                    format_log(
                        "supervisor",
                        "retry",
                        "INFO",
                        f"completed after {retry_count} retries",
                    ),
                )

        self._on_task_done(task_id, exit_code, error, metadata=metadata)

    def _on_host_log(self, task_id: str, line: str) -> None:
        task_id = str(task_id or "").strip()
        if task_id:
            proxy = getattr(self, "_task_event_proxies", {}).get(task_id)
            if proxy is not None:
                proxy.enqueue_host_log(task_id, line)
                return
        self._on_task_log(task_id, line)

    def _on_host_pr_url(self, task_id: str, pr_url: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.gh_pr_url = str(pr_url or "").strip()
        task.git = derive_task_git_metadata(task)
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = stain_color(env.color) if env else None
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
        spinner = stain_color(env.color) if env else None
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
                spinner = stain_color(env.color) if env else None
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        if "docker pull" in cleaned and (task.status or "").lower() != "pulling":
            task.status = "pulling"
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._schedule_save()

    def _on_task_state(self, task_id: str, state: dict[str, Any]) -> None:
        task = self._tasks.get(task_id)
        bridge = self._bridges.get(task_id)
        if task is None:
            return

        current = (task.status or "").lower()
        if current in {"cancelled", "killed"}:
            self._clear_ide_novnc_auto_open_state(task_id)
            if bridge and bridge.container_id:
                task.container_id = bridge.container_id
            finished_at = parse_docker_time(state.get("FinishedAt"))
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

        started_at = parse_docker_time(state.get("StartedAt"))
        finished_at = parse_docker_time(state.get("FinishedAt"))
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
        spinner = stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._maybe_schedule_ide_novnc_auto_open(task)
        self._schedule_save()

    def _remember_ide_safe_mode_if_needed(self, task: Task) -> None:
        launch_mode = str(getattr(task, "launch_mode", "") or "").strip().lower()
        if launch_mode != "ide":
            return
        ide_system = str(getattr(task, "ide_system", "") or "").strip().lower()
        if not ide_system:
            return
        saw_retry_marker = any(
            "safe-retry-triggered" in str(line or "") for line in (task.logs or [])
        )
        if not saw_retry_marker:
            return
        env_id = str(getattr(task, "environment_id", "") or "").strip()
        if not env_id:
            return
        env = self._environments.get(env_id)
        if env is None:
            return
        existing_map = getattr(env, "ide_safe_mode_by_system", {})
        safe_map = dict(existing_map) if isinstance(existing_map, dict) else {}
        if bool(safe_map.get(ide_system, False)):
            return
        safe_map[ide_system] = True
        env.ide_safe_mode_by_system = safe_map
        try:
            save_environment(env)
        except Exception as exc:
            self._on_task_log(
                task.task_id,
                format_log(
                    "ide",
                    "retry",
                    "WARN",
                    f"failed to persist safe mode for ide={ide_system}: {exc}",
                ),
            )
            return
        self._environments[env.env_id] = env
        self._on_task_log(
            task.task_id,
            format_log(
                "ide",
                "retry",
                "INFO",
                f"remembered safe mode for ide={ide_system}",
            ),
        )

    def _on_task_done(
        self,
        task_id: str,
        exit_code: int,
        error: object,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        self._clear_ide_novnc_auto_open_state(task_id)
        try:
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"Task {task_id}: task completed, preparing finalization (state={task.status}, exit_code={exit_code})",
                ),
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
                self._on_task_log(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "ERROR",
                        f"task failed: {task.error}",
                    ),
                )
            else:
                task.status = "done" if int(exit_code) == 0 else "failed"

            self._remember_ide_safe_mode_if_needed(task)
            task.git = derive_task_git_metadata(task)

            # Validate git metadata for cloned repo tasks
            if task.requires_git_metadata():
                from agents_runner.ui.task_git_metadata import validate_git_metadata

                is_valid, error_msg = validate_git_metadata(task.git)
                if not is_valid:
                    self._on_task_log(
                        task_id,
                        format_log(
                            "host",
                            "metadata",
                            "WARN",
                            f"git metadata validation failed: {error_msg}",
                        ),
                    )
                    # Note: We don't fail the task itself, as the code execution may have succeeded
                    # The metadata issue will be flagged but won't affect task completion status

            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            if user_stop is None:
                QApplication.beep()

            self._on_task_log(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"task marked complete: status={task.status} exit_code={task.exit_code}",
                ),
            )
            self._try_start_queued_tasks()
            self._refresh_new_task_agent_info()

            if (task.finalization_state or "").lower().strip() == "done":
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "DEBUG",
                        f"Task {task_id}: skipping finalization (reason=already done, state=done)",
                    ),
                )
                return

            # SYNCHRONIZATION: Set finalization_state to "pending" BEFORE calling _queue_task_finalization().
            # This atomic state change prevents recovery_tick from queuing duplicate finalization work.
            # The recovery_tick checks finalization_state and skips tasks that are "pending" or "running".
            # Combined with thread existence checks in _queue_task_finalization(), this provides
            # race-free coordination between task_done and recovery_tick finalization triggers.
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"Task {task_id}: state transition (state=None→pending, reason=task_done)",
                ),
            )
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
                    format_log(
                        "gh",
                        "cleanup",
                        "WARN",
                        "cleanup skipped: state path not available",
                    ),
                )
                return

            self._on_task_log(
                task_id,
                format_log("gh", "cleanup", "INFO", "cleaning up task workspace"),
            )
            data_dir = os.path.dirname(state_path)
            cleanup_success = cleanup_task_workspace(
                env_id=env_id,
                task_id=task_id,
                data_dir=data_dir,
                on_log=lambda msg: self._on_task_log(task_id, msg),
            )
            if cleanup_success:
                self._on_task_log(
                    task_id,
                    format_log("gh", "cleanup", "INFO", "task workspace cleaned"),
                )
        except Exception as cleanup_exc:
            self._on_task_log(
                task_id,
                format_log("gh", "cleanup", "ERROR", f"cleanup failed: {cleanup_exc}"),
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
                timeout_s = float(
                    getattr(runner_config, "artifact_collection_timeout_s")
                )
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
            self.host_log.emit(
                task.task_id,
                format_log(
                    "host",
                    "artifacts",
                    "INFO",
                    "collecting artifacts from container...",
                ),
            )
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
                    format_log(
                        "host",
                        "finalize",
                        "INFO",
                        f"artifact collection finished in {elapsed_s:.1f}s ({len(artifact_uuids)} artifact(s))",
                    ),
                )
                if artifact_uuids:
                    self.host_artifacts.emit(task.task_id, artifact_uuids)
            except Exception as exc:
                elapsed_s = time.monotonic() - start
                self.host_log.emit(
                    task.task_id,
                    format_log(
                        "host",
                        "artifacts",
                        "ERROR",
                        f"artifact collection failed/timeout: {exc} (elapsed {elapsed_s:.1f}s)",
                    ),
                )

        threading.Thread(target=_worker, daemon=True).start()
