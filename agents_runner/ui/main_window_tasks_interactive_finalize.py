from __future__ import annotations

import os
import threading

from datetime import datetime
from datetime import timezone

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_display import format_agent_markdown_link
from agents_runner.agent_display import get_agent_display_name
from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.gh_management import commit_push_and_pr
from agents_runner.gh_management import GhManagementError
from agents_runner.pr_metadata import load_pr_metadata
from agents_runner.pr_metadata import normalize_pr_title
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

        try:
            task.exit_code = int(exit_code)
        except Exception:
            task.exit_code = 1
        task.finished_at = datetime.now(tz=timezone.utc)
        task.status = "done" if (task.exit_code or 0) == 0 else "failed"

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()
        QApplication.beep()
        self._on_task_log(task_id, f"[interactive] exited with {task.exit_code}")

        if (
            normalize_gh_management_mode(task.gh_management_mode)
            == GH_MANAGEMENT_GITHUB
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
    ) -> None:
        if not repo_root or not branch:
            return

        # Get task info for cleanup
        task = self._tasks.get(task_id)
        env_id = str(task.environment_id or "").strip() if task and hasattr(task, "environment_id") else ""
        
        try:
            prompt_line = (prompt_text or "").strip().splitlines()[0] if prompt_text else ""
            default_title = f"Agent Runner: {prompt_line or task_id}"
            default_title = normalize_pr_title(default_title, fallback=default_title)

            agent_display = get_agent_display_name(agent_cli) if agent_cli else "Agent"
            agent_link = (
                format_agent_markdown_link(agent_cli) if agent_cli else agent_display
            )
            runners_link = "[Agents Runner](https://github.com/Midori-AI-OSS/Agents-Runner)"

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
                    task_id, f"[gh] using PR metadata from {pr_metadata_path}"
                )
            title = (
                normalize_pr_title(str(metadata.title or ""), fallback=default_title)
                if metadata is not None
                else default_title
            )
            body = str(metadata.body or "").strip() if metadata is not None else ""
            if not body:
                body = default_body

            self.host_log.emit(
                task_id, f"[gh] preparing PR from {branch} -> {base_branch or 'auto'}"
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
                self.host_log.emit(task_id, f"[gh] failed: {exc}")
                return
            except Exception as exc:
                self.host_log.emit(task_id, f"[gh] failed: {exc}")
                return

            if pr_url is None:
                self.host_log.emit(task_id, "[gh] no changes to commit; skipping PR")
                return
            if pr_url == "":
                self.host_log.emit(
                    task_id,
                    "[gh] pushed branch; PR creation skipped (gh disabled or missing)",
                )
                return
            self.host_pr_url.emit(task_id, pr_url)
            self.host_log.emit(task_id, f"[gh] PR: {pr_url}")
        finally:
            # Clean up task-specific repo after PR creation (or failure)
            # This ensures each task gets a fresh clone and prevents git conflicts
            if env_id and task_id:
                try:
                    # Validate state_path before using
                    state_path = getattr(self, "_state_path", "")
                    if not state_path:
                        self.host_log.emit(
                            task_id, "[gh] cleanup skipped: state path not available"
                        )
                        return
                    
                    self.host_log.emit(task_id, "[gh] cleaning up task workspace")
                    data_dir = os.path.dirname(state_path)
                    cleanup_success = cleanup_task_workspace(
                        env_id=env_id,
                        task_id=task_id,
                        data_dir=data_dir,
                        on_log=lambda msg: self.host_log.emit(task_id, msg),
                    )
                    if cleanup_success:
                        self.host_log.emit(task_id, "[gh] task workspace cleaned")
                except Exception as cleanup_exc:
                    self.host_log.emit(
                        task_id, f"[gh] cleanup failed: {cleanup_exc}"
                    )
