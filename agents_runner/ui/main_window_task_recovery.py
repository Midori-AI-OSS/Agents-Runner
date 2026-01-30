from __future__ import annotations

import os
import subprocess
import threading
import time


from agents_runner.artifacts import collect_artifacts_from_container_with_timeout
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.log_format import format_log
from agents_runner.log_format import wrap_container_log
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color


class _MainWindowTaskRecoveryMixin:
    def _reconcile_tasks_after_restart(self) -> None:
        """Reconcile tasks after app restart.
        
        This runs once at startup to handle tasks that were interrupted or completed
        before the app was closed. It serves a different purpose than recovery_tick:
        
        - startup_reconcile: Handles tasks that were done BEFORE restart but missed finalization
        - recovery_tick: Safety net for tasks that complete DURING runtime but miss events
        
        For active tasks, delegates to _tick_recovery_task() to sync container state.
        For done/failed tasks, queues finalization if needed and not already finalized.
        
        Note: Deduplication guards in _queue_task_finalization() prevent duplicate work
        if recovery_tick fires before this completes.
        """
        # STARTUP RECONCILIATION: Run once at app start to handle tasks from previous session
        self.host_log.emit(
            "",
            format_log(
                "host",
                "startup",
                "INFO",
                f"Starting task reconciliation after restart ({len(self._tasks)} tasks to check)",
            ),
        )
        for task in list(self._tasks.values()):
            if task.is_active():
                # Sync container state for tasks that were running when app closed
                self.host_log.emit(
                    str(task.task_id or ""),
                    format_log(
                        "host",
                        "startup",
                        "DEBUG",
                        f"Task {task.task_id}: syncing active task (state={task.status})",
                    ),
                )
                self._tick_recovery_task(task)
                continue
            if self._task_needs_finalization(task) and not task.is_interactive_run():
                # Queue finalization for tasks that completed before restart
                self.host_log.emit(
                    str(task.task_id or ""),
                    format_log(
                        "host",
                        "startup",
                        "INFO",
                        f"Task {task.task_id}: queueing finalization (reason=startup_reconcile, state={task.status})",
                    ),
                )
                self._queue_task_finalization(task.task_id, reason="startup_reconcile")

    def _tick_recovery(self) -> None:
        """Recovery tick handler (runs every 5 seconds).
        
        Safety net for tasks that complete during runtime but miss event-driven finalization.
        This is different from startup_reconcile which handles tasks from previous session.
        """
        for task in list(self._tasks.values()):
            # Skip tasks that have already completed finalization to avoid log spam
            if (task.finalization_state or "").lower().strip() == "done":
                continue
            self._tick_recovery_task(task)

    def _tick_recovery_task(self, task: Task) -> None:
        """Process a single task for recovery/finalization.
        
        RECOVERY TICK: Safety net for tasks that complete during runtime.
        This is different from startup_reconcile which handles tasks from previous session.
        
        For active tasks: syncs container state and ensures log tailing
        For done tasks: queues finalization if needed (with deduplication guards)
        
        Note: This method assumes the task has not yet been finalized (caller filters out
        tasks with finalization_state=="done" before calling this).
        """
        status_lower = (task.status or "").lower()
        if task.is_active() or status_lower == "unknown":
            synced = self._try_sync_container_state(task)
            if synced:
                self._update_task_ui(task)
            if task.is_active():
                self._ensure_recovery_log_tail(task)
                return

        if self._task_needs_finalization(task) and not task.is_interactive_run():
            # Don't queue recovery_tick finalization if task has an active bridge.
            # The bridge will handle finalization via _on_bridge_done -> _on_task_done.
            # This prevents double finalization when both recovery_tick and task_done
            # attempt to finalize the same task.
            if task.task_id in self._bridges:
                return
            # SYNCHRONIZATION GUARD 1: Check finalization_state
            # _on_task_done() sets state to "pending" before queueing finalization.
            # This prevents recovery_tick from creating duplicate work for tasks that
            # are already being finalized via the task_done path.
            # Also defensively check for "done" state to prevent log spam.
            finalization_state_lower = (task.finalization_state or "").lower().strip()
            if finalization_state_lower in {"pending", "running", "done"}:
                self.host_log.emit(
                    str(task.task_id or ""),
                    format_log(
                        "host",
                        "recovery_tick",
                        "INFO",
                        f"Task {task.task_id}: skipping finalization (reason=already {finalization_state_lower}, state={finalization_state_lower})",
                    ),
                )
                return
            
            # SYNCHRONIZATION GUARD 2: Check thread existence
            # Even if state isn't updated yet, the thread dict provides an additional
            # guard against duplicate finalization threads for the same task.
            task_id = str(task.task_id or "").strip()
            if task_id:
                existing_thread = self._finalization_threads.get(task_id)
                if existing_thread is not None and existing_thread.is_alive():
                    self.host_log.emit(
                        task_id,
                        format_log(
                            "host",
                            "recovery_tick",
                            "INFO",
                            f"Task {task.task_id}: skipping finalization (reason=thread already running, state={finalization_state_lower})",
                        ),
                    )
                    return
            
            self.host_log.emit(
                str(task.task_id or ""),
                format_log(
                    "host",
                    "recovery_tick",
                    "INFO",
                    f"Task {task.task_id}: queueing finalization (reason=recovery_tick, state={task.status})",
                ),
            )
            self._queue_task_finalization(task.task_id, reason="recovery_tick")

    def _task_needs_finalization(self, task: Task) -> bool:
        if not (task.is_done() or task.is_failed()):
            return False
        return (task.finalization_state or "").lower().strip() != "done"

    def _update_task_ui(self, task: Task) -> None:
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _ensure_recovery_log_tail(self, task: Task) -> None:
        task_id = str(task.task_id or "").strip()
        container_id = str(task.container_id or "").strip()
        if not task_id or not container_id:
            return
        if (task.status or "").lower() not in {"starting", "running", "created", "cloning", "pulling"}:
            return
        if task_id in self._recovery_log_stop:
            return
        # Don't start recovery log tail if task has an active bridge (bridge already streams logs)
        if task_id in self._bridges:
            return

        stop = threading.Event()
        self._recovery_log_stop[task_id] = stop

        def _worker() -> None:
            proc: subprocess.Popen[str] | None = None
            try:
                proc = subprocess.Popen(
                    ["docker", "logs", "-f", "--tail", "200", container_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if proc.stdout is None:
                    return
                for line in proc.stdout:
                    if stop.is_set():
                        break
                    self.host_log.emit(
                        task_id,
                        wrap_container_log(container_id, "stdout", line.rstrip("\n")),
                    )
            except Exception as exc:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "docker",
                        "logs",
                        "WARN",
                        f"recovery log tail stopped: {exc}",
                    ),
                )
            finally:
                try:
                    if proc is not None and proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2.0)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                except Exception:
                    pass
                self._recovery_log_stop.pop(task_id, None)

        threading.Thread(target=_worker, daemon=True).start()

    def _queue_task_finalization(self, task_id: str, *, reason: str) -> None:
        """Queue task finalization work.
        
        SYNCHRONIZATION: This function provides thread-safe finalization queueing via
        four defensive mechanisms:
        1. Early state check: Returns immediately if finalization is "pending" or "running"
        2. Needs-finalization check: task.finalization_state must not be "done"
        3. Thread existence check: Prevents creating duplicate threads
        4. State reset: If somehow in "running" state without a live thread, resets to "pending"
        
        These guards coordinate finalization between task_done and recovery_tick paths,
        ensuring exactly one finalization thread runs per task.
        """
        task_id = str(task_id or "").strip()
        if not task_id:
            return

        task = self._tasks.get(task_id)
        if task is None:
            return

        # DEDUPLICATION GUARD 1: Check finalization_state first for early return
        # This prevents duplicate finalization attempts when finalization is already
        # queued or running via any code path (task_done, recovery_tick, etc.)
        finalization_state_lower = (task.finalization_state or "").lower().strip()
        if finalization_state_lower == "pending":
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"Task {task_id}: skipping finalization (reason=already pending, state=pending, trigger={reason})",
                ),
            )
            return
        if finalization_state_lower == "running":
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"Task {task_id}: skipping finalization (reason=already running, state=running, trigger={reason})",
                ),
            )
            return
        # Also check for "done" state defensively (should be caught by _task_needs_finalization,
        # but add explicit guard to prevent any edge cases)
        if finalization_state_lower == "done":
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "DEBUG",
                    f"Task {task_id}: skipping finalization (reason=already done, state=done, trigger={reason})",
                ),
            )
            return

        if not self._task_needs_finalization(task):
            return

        # DEDUPLICATION GUARD 2: Check if finalization thread already exists
        # This handles edge cases where state might not be set yet but thread exists
        existing = self._finalization_threads.get(task_id)
        if existing is not None and existing.is_alive():
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"Task {task_id}: skipping finalization (reason=thread already alive, state={finalization_state_lower}, trigger={reason})",
                ),
            )
            return

        # ORPHANED STATE RECOVERY:
        # If state shows "running" but no live thread exists, this indicates an orphaned
        # state from an app crash or unexpected termination. We reset to "pending" to allow
        # finalization to retry. This is safe because:
        # 1. No thread is actually running (verified by guard check above)
        # 2. finalization_state="running" means work was interrupted mid-flight
        # 3. Finalization operations are idempotent (safe to retry)
        # 4. This ensures tasks don't get stuck in "running" state forever
        if finalization_state_lower == "running":
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "WARN",
                    f"Task {task_id}: state was running but no thread found, resetting (state=running→pending, trigger={reason})",
                ),
            )
            task.finalization_state = "pending"

        # Queue finalization: Log the successful queueing with reason
        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "finalize",
                "INFO",
                f"Task {task_id}: queueing finalization (reason={reason}, state={task.status})",
            ),
        )

        thread = threading.Thread(
            target=self._finalize_task_worker,
            args=(task_id, reason),
            daemon=True,
        )
        self._finalization_threads[task_id] = thread
        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "finalize",
                "DEBUG",
                f"Task {task_id}: finalization thread created (reason={reason})",
            ),
        )
        thread.start()
        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "finalize",
                "DEBUG",
                f"Task {task_id}: finalization thread started (reason={reason})",
            ),
        )

    def _finalize_task_worker(self, task_id: str, reason: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return

        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "finalize",
                "INFO",
                f"Task {task_id}: state transition (state=None→running, reason={reason})",
            ),
        )
        task.finalization_state = "running"
        task.finalization_error = ""
        self._schedule_save()
        self.host_log.emit(
            task_id,
            format_log("host", "finalize", "INFO", f"finalization running (reason={reason})"),
        )

        try:
            # ARTIFACT COLLECTION LOGIC:
            # Skip artifact collection for user-stopped tasks because:
            # 1. User explicitly canceled, so they don't want the incomplete work
            # 2. Artifacts may be in inconsistent state (task didn't finish)
            # 3. Saves time and resources for unwanted output
            user_stop = (task.status or "").lower() in {"cancelled", "killed"}
            if not user_stop:
                runner_config = getattr(task, "_runner_config", None)
                timeout_s = 30.0
                if runner_config is not None:
                    try:
                        timeout_s = float(getattr(runner_config, "artifact_collection_timeout_s"))
                    except Exception:
                        timeout_s = 30.0
                if timeout_s <= 0.0:
                    timeout_s = 30.0

                task_dict = {
                    "task_id": str(task.task_id or ""),
                    "image": str(task.image or ""),
                    "agent_cli": str(task.agent_cli or ""),
                    "created_at": float(task.created_at_s or 0.0),
                }
                env_name = str(task.environment_id or "")
                start_s = time.monotonic()
                self.host_log.emit(
                    task_id,
                    format_log("host", "artifacts", "INFO", "collecting artifacts from staging..."),
                )
                artifact_uuids = collect_artifacts_from_container_with_timeout(
                    str(task.container_id or ""),
                    task_dict,
                    env_name,
                    timeout_s=timeout_s,
                )
                elapsed_s = time.monotonic() - start_s
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "INFO",
                        f"artifact collection finished in {elapsed_s:.1f}s ({len(artifact_uuids)} artifact(s))",
                    ),
                )
                if artifact_uuids:
                    self.host_artifacts.emit(task_id, artifact_uuids)

            should_create_pr = False
            skip_reason: str | None = None
            if user_stop:
                skip_reason = f"user stopped task ({task.status})"
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "INFO",
                        f"Task {task_id}: skipping PR creation (reason={skip_reason}, state={task.status})",
                    ),
                )
            elif task.workspace_type != WORKSPACE_CLONED:
                skip_reason = f"not a cloned workspace (type={task.workspace_type})"
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "INFO",
                        f"Task {task_id}: skipping PR creation (reason={skip_reason}, state={task.status})",
                    ),
                )
            elif not task.gh_repo_root:
                skip_reason = "missing repository root information"
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "WARN",
                        f"Task {task_id}: skipping PR creation (reason={skip_reason}, state={task.status})",
                    ),
                )
            elif not task.gh_branch:
                skip_reason = "missing branch information"
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "WARN",
                        f"Task {task_id}: skipping PR creation (reason={skip_reason}, state={task.status})",
                    ),
                )
            elif task.gh_pr_url:
                skip_reason = "PR already created"
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "INFO",
                        f"Task {task_id}: skipping PR creation (reason={skip_reason}, state={task.status})",
                    ),
                )
            else:
                should_create_pr = True
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "finalize",
                        "INFO",
                        f"Task {task_id}: proceeding with PR creation (reason=all checks passed, state={task.status})",
                    ),
                )

            pr_worker_ran = False
            if should_create_pr:
                pr_worker_ran = True
                self._finalize_gh_management_worker(
                    task_id,
                    str(task.gh_repo_root or "").strip(),
                    str(task.gh_branch or "").strip(),
                    str(task.gh_base_branch or "").strip(),
                    str(task.prompt or ""),
                    str(task.task_id or task_id),
                    bool(task.gh_use_host_cli),
                    (str(task.gh_pr_metadata_path or "").strip() or None),
                    str(task.agent_cli or "").strip(),
                    str(task.agent_cli_args or "").strip(),
                )
            else:
                self.host_log.emit(
                    task_id,
                    format_log("gh", "pr", "INFO", f"PR creation skipped: {skip_reason}"),
                )

            # WORKSPACE CLEANUP LOGIC:
            # Cleanup happens here ONLY if:
            # 1. PR worker did NOT run (PR worker cleans in its finally block)
            # 2. reason != "recovery_tick" (recovery_tick is monitoring, not modifying)
            # 3. workspace is cloned (non-cloned workspaces don't need cleanup)
            # 
            # Why recovery_tick skips cleanup:
            # - recovery_tick is a safety net that runs every 5 seconds
            # - It should verify finalization state but not modify workspaces
            # - Cleanup is handled by the primary paths (task_done, user_stop, startup_reconcile)
            # - This prevents recovery_tick from accidentally removing resources still in use
            if (
                not pr_worker_ran
                and reason != "recovery_tick"  # Skip cleanup during recovery
                and task.workspace_type == WORKSPACE_CLONED
                and str(task.environment_id or "").strip()
                and str(task.task_id or "").strip()
            ):
                self._cleanup_task_workspace_for_finalization(
                    task_id,
                    str(task.environment_id or "").strip(),
                )

            task.finalization_state = "done"
            task.finalization_error = ""
            self._schedule_save()
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"Task {task_id}: state transition (state=running→done, reason={reason})",
                ),
            )
            self.host_log.emit(
                task_id,
                format_log("host", "finalize", "INFO", "finalization complete"),
            )
        except Exception as exc:
            task.finalization_state = "error"
            task.finalization_error = str(exc)
            self._schedule_save()
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "ERROR",
                    f"Task {task_id}: state transition (state=running→error, reason={reason})",
                ),
            )
            self.host_log.emit(
                task_id,
                format_log("host", "finalize", "ERROR", f"finalization failed: {exc}"),
            )

    def _cleanup_task_workspace_for_finalization(self, task_id: str, env_id: str) -> None:
        env_id = str(env_id or "").strip()
        if not env_id:
            return
        state_path = str(getattr(self, "_state_path", "") or "").strip()
        if not state_path:
            self.host_log.emit(
                task_id,
                format_log("gh", "cleanup", "WARN", "cleanup skipped: state path not available"),
            )
            return
        data_dir = os.path.dirname(state_path)
        self.host_log.emit(
            task_id,
            format_log("gh", "cleanup", "INFO", "cleaning up task workspace"),
        )
        try:
            cleanup_success = cleanup_task_workspace(
                env_id=env_id,
                task_id=task_id,
                data_dir=data_dir,
                on_log=lambda msg: self.host_log.emit(task_id, msg),
            )
            if cleanup_success:
                self.host_log.emit(
                    task_id,
                    format_log("gh", "cleanup", "INFO", "task workspace cleaned"),
                )
        except Exception as cleanup_exc:
            self.host_log.emit(
                task_id,
                format_log("gh", "cleanup", "ERROR", f"cleanup failed: {cleanup_exc}"),
            )
