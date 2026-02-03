from __future__ import annotations

import os
import threading
import time

from datetime import datetime
from datetime import timezone

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_display import format_agent_markdown_link
from agents_runner.agent_display import get_agent_display_name
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.gh_management import commit_push_and_pr
from agents_runner.gh_management import GhManagementError
from agents_runner.log_format import format_log
from agents_runner.pr_metadata import load_pr_metadata
from agents_runner.pr_metadata import normalize_pr_title
from agents_runner.ui.task_git_metadata import derive_task_git_metadata
from agents_runner.ui.utils import _stain_color


class _MainWindowTasksInteractiveFinalizeMixin:
    def _on_interactive_finished(self, task_id: str, exit_code: int) -> None:
        task_id = str(task_id or "").strip()
        watch = self._interactive_watch.pop(task_id, None)
        if watch is not None:
            _, stop = watch
            stop.set()

        task = self._tasks.get(task_id)
        if task is None:
            return

        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "interactive",
                "INFO",
                f"Task {task_id}: interactive run finished (exit_code={exit_code}, state={task.status})",
            ),
        )

        try:
            task.exit_code = int(exit_code)
        except Exception:
            task.exit_code = 1
        task.finished_at = datetime.now(tz=timezone.utc)
        task.status = "done" if (task.exit_code or 0) == 0 else "failed"
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

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()
        QApplication.beep()
        self._on_task_log(
            task_id,
            format_log("host", "interactive", "INFO", f"exited with {task.exit_code}"),
        )

        # Interactive tasks handle PR creation immediately via user dialog, then mark finalization done
        # This is different from agent tasks which queue finalization work for background processing
        if (
            task.workspace_type == WORKSPACE_CLONED
            and task.gh_repo_root
            and task.gh_branch
            and not task.gh_pr_url
        ):
            base = str(task.gh_base_branch or "").strip()
            base_display = base or "auto"
            message = f"Interactive run finished.\n\nCreate a PR from {task.gh_branch} -> {base_display}?"
            if (
                QMessageBox.question(self, "Create pull request?", message)
                == QMessageBox.StandardButton.Yes
            ):
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "interactive",
                        "INFO",
                        f"Task {task_id}: creating PR after interactive run (branch={task.gh_branch}, base={base_display})",
                    ),
                )
                threading.Thread(
                    target=self._finalize_gh_management_worker,
                    args=(
                        task_id,
                        str(task.gh_repo_root or "").strip(),
                        str(task.gh_branch or "").strip(),
                        str(base).strip(),
                        str(task.prompt or ""),
                        str(task.task_id or task_id),
                        bool(task.gh_use_host_cli),
                        None,
                        str(task.agent_cli or "").strip(),
                        str(task.agent_cli_args or "").strip(),
                    ),
                    daemon=True,
                ).start()
            else:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "interactive",
                        "INFO",
                        f"Task {task_id}: PR creation declined by user",
                    ),
                )

        # Mark finalization done for interactive tasks (PR creation handled synchronously above)
        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "interactive",
                "INFO",
                f"Task {task_id}: state transition (state=None→done, reason=interactive_finished)",
            ),
        )
        task.finalization_state = "done"
        task.finalization_error = ""
        self._schedule_save()

    def _finalize_gh_management_worker(
        self,
        task_id: str,
        repo_root: str,
        branch: str,
        base_branch: str,
        prompt_text: str,
        task_token: str,
        use_gh: bool,
        pr_metadata_path: str | None = None,
        agent_cli: str = "",
        agent_cli_args: str = "",
        is_override: bool = False,
    ) -> None:
        if not repo_root or not branch:
            return

        start_s = time.monotonic()

        # Get task info for cleanup - extract environment_id safely (needed even on early-return paths)
        task = self._tasks.get(task_id)
        env_id = ""
        if task and hasattr(task, "environment_id"):
            env_id = str(task.environment_id or "").strip()

        try:
            # Step 1: Pre-flight validation
            self.host_log.emit(
                task_id,
                format_log("gh", "pr", "INFO", "[1/6] Validating repository..."),
            )

            from agents_runner.gh.pr_validation import check_existing_pr
            from agents_runner.gh.pr_validation import validate_pr_prerequisites

            checks = validate_pr_prerequisites(
                repo_root=repo_root,
                branch=branch,
                use_gh=use_gh,
            )

            # Check for failures
            failed_checks = [(name, msg) for name, passed, msg in checks if not passed]
            if failed_checks:
                for name, msg in failed_checks:
                    self.host_log.emit(
                        task_id,
                        format_log(
                            "gh", "pr", "ERROR", f"validation failed: {name}: {msg}"
                        ),
                    )
                return

            # Check for existing PR (informational)
            existing_pr = check_existing_pr(repo_root, branch)
            if existing_pr:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        f"[2/6] Pull request already exists: {existing_pr}",
                    ),
                )
                self.host_pr_url.emit(task_id, existing_pr)
                if task:
                    task.gh_pr_url = existing_pr
                    self._schedule_save()
                return

            self.host_log.emit(
                task_id,
                format_log(
                    "gh", "pr", "INFO", "[2/6] No existing PR found, proceeding..."
                ),
            )

            self.host_log.emit(
                task_id,
                format_log("gh", "pr", "INFO", "[3/6] Preparing PR metadata..."),
            )

            prompt_line = (
                (prompt_text or "").strip().splitlines()[0] if prompt_text else ""
            )
            default_title = f"Agent Runner: {prompt_line or task_id}"
            default_title = normalize_pr_title(default_title, fallback=default_title)

            agent_display = get_agent_display_name(agent_cli) if agent_cli else "Agent"
            agent_link = (
                format_agent_markdown_link(agent_cli) if agent_cli else agent_display
            )
            runners_link = (
                "[Agents Runner](https://github.com/Midori-AI-OSS/Agents-Runner)"
            )

            default_body = (
                f"Automated by {runners_link}.\n\n"
                f"Agent: {agent_link}\n\n"
                f"Task: {task_token}\n\n"
                "Prompt:\n"
                f"{(prompt_text or '').strip()}\n"
            )
            metadata = (
                load_pr_metadata(pr_metadata_path or "") if pr_metadata_path else None
            )
            if metadata is not None and (metadata.title or metadata.body):
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh", "pr", "INFO", f"using PR metadata from {pr_metadata_path}"
                    ),
                )
            title = (
                normalize_pr_title(str(metadata.title or ""), fallback=default_title)
                if metadata is not None
                else default_title
            )
            body = str(metadata.body or "").strip() if metadata is not None else ""
            if not body:
                body = default_body

            # Add override note for non-cloned-repo modes
            if is_override:
                body += "\n\n---\n**Note:** This is an override PR created manually for a cloned repo environment."

            self.host_log.emit(
                task_id,
                format_log(
                    "gh",
                    "pr",
                    "INFO",
                    f"[4/6] Creating PR from {branch} -> {base_branch or 'auto'}",
                ),
            )
            try:
                pr_url = commit_push_and_pr(
                    repo_root,
                    branch=branch,
                    base_branch=base_branch,
                    title=title,
                    body=body,
                    use_gh=bool(use_gh),
                    agent_cli=agent_cli,
                    agent_cli_args=agent_cli_args,
                )
            except GhManagementError as exc:
                self.host_log.emit(
                    task_id, format_log("gh", "pr", "ERROR", f"failed: {exc}")
                )
                return
            except Exception as exc:
                self.host_log.emit(
                    task_id, format_log("gh", "pr", "ERROR", f"failed: {exc}")
                )
                return

            if pr_url is None:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh", "pr", "INFO", "[5/6] No changes to commit; skipping PR"
                    ),
                )
                return
            if pr_url == "":
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        "[5/6] Branch pushed; PR creation skipped (gh disabled or missing)",
                    ),
                )
                return
            self.host_log.emit(
                task_id,
                format_log(
                    "gh", "pr", "INFO", f"[6/6] PR created successfully: {pr_url}"
                ),
            )
            self.host_pr_url.emit(task_id, pr_url)

            # Update task PR URL
            if task:
                task.gh_pr_url = pr_url
                self._schedule_save()
        finally:
            # Clean up task-specific repo after PR creation (or failure)
            # This ensures each task gets a fresh clone and prevents git conflicts
            if env_id and task_id:
                try:
                    # Validate state_path before using
                    state_path = getattr(self, "_state_path", "")
                    if not state_path:
                        self.host_log.emit(
                            task_id,
                            format_log(
                                "gh",
                                "cleanup",
                                "WARN",
                                "cleanup skipped: state path not available",
                            ),
                        )
                    else:
                        self.host_log.emit(
                            task_id,
                            format_log(
                                "gh", "cleanup", "INFO", "cleaning up task workspace"
                            ),
                        )
                        data_dir = os.path.dirname(state_path)
                        cleanup_success = cleanup_task_workspace(
                            env_id=env_id,
                            task_id=task_id,
                            data_dir=data_dir,
                            on_log=lambda msg: self.host_log.emit(task_id, msg),
                        )
                        if cleanup_success:
                            self.host_log.emit(
                                task_id,
                                format_log(
                                    "gh", "cleanup", "INFO", "task workspace cleaned"
                                ),
                            )
                except Exception as cleanup_exc:
                    self.host_log.emit(
                        task_id,
                        format_log(
                            "gh", "cleanup", "ERROR", f"cleanup failed: {cleanup_exc}"
                        ),
                    )
            elapsed_s = time.monotonic() - start_s
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"PR preparation finished in {elapsed_s:.1f}s",
                ),
            )
