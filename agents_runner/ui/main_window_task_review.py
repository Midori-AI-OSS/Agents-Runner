from __future__ import annotations

import threading

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.log_format import format_log


class _MainWindowTaskReviewMixin:
    def _on_task_pr_requested(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        task = self._tasks.get(task_id)
        if task is None:
            return

        env = self._environments.get(task.environment_id)
        is_git_locked = bool(getattr(task, "gh_management_locked", False))
        if not is_git_locked and env:
            is_git_locked = bool(getattr(env, "gh_management_locked", False))
        
        if not is_git_locked:
            QMessageBox.information(
                self,
                "PR not available",
                "PR creation is only available for git-locked environments.",
            )
            return

        gh_mode = normalize_gh_management_mode(task.gh_management_mode)
        is_github_mode = gh_mode == GH_MANAGEMENT_GITHUB

        # Handle existing PR URL
        pr_url = str(task.gh_pr_url or "").strip()
        if pr_url.startswith("http"):
            if not QDesktopServices.openUrl(QUrl(pr_url)):
                QMessageBox.warning(self, "Failed to open PR", pr_url)
            return

        # Get repo root and branch, setting defaults for non-GitHub modes
        repo_root = str(task.gh_repo_root or "").strip()
        branch = str(task.gh_branch or "").strip()
        
        # For non-GitHub locked envs, we need to set up branch/repo if missing
        # Try getting from environment's host_workdir
        if not repo_root and env:
            repo_root = str(getattr(env, "host_workdir", "") or "").strip()
            # Persist the repo_root to the task for future use
            if repo_root:
                task.gh_repo_root = repo_root
        
        # If still missing, try to get from task's host_workdir
        if not repo_root:
            repo_root = str(task.host_workdir or "").strip()
            if repo_root:
                task.gh_repo_root = repo_root
        
        # If still missing, try to repair git metadata
        if not repo_root and task.requires_git_metadata():
            from agents_runner.ui.task_repair import repair_task_git_metadata
            success, msg = repair_task_git_metadata(
                task,
                state_path=self._state_path,
                environments=self._environments,
            )
            if success:
                # After repair, re-read gh_repo_root (repair should have populated it)
                repo_root = str(task.gh_repo_root or "").strip()
                # If still missing, try fallback to host_workdir
                if not repo_root:
                    repo_root = str(task.host_workdir or "").strip()
                    if repo_root:
                        task.gh_repo_root = repo_root
                self._schedule_save()
        
        if not branch:
            branch = f"midoriaiagents/{task_id}"
        
        if not repo_root:
            QMessageBox.warning(
                self, "PR not available",
                "Cannot locate the repository path for this task.\n\n"
                "This may occur if:\n"
                "• The repository clone hasn't completed yet\n"
                "• The clone operation failed\n"
                "• The task was reloaded before the clone finished\n\n"
                "Wait for the task to complete, then try again."
            )
            return

        if task.is_active():
            QMessageBox.information(
                self,
                "Task still running",
                "Wait for the task to finish before creating a PR.",
            )
            return

        base_branch = str(task.gh_base_branch or "").strip()
        base_display = base_branch or "auto"
        message = f"Create a PR from {branch} -> {base_display}?\n\nThis will commit and push any local changes."
        if (
            QMessageBox.question(self, "Create pull request?", message)
            != QMessageBox.StandardButton.Yes
        ):
            return

        prompt_text = str(task.prompt or "")
        task_token = str(task.task_id or task_id)
        pr_metadata_path = str(task.gh_pr_metadata_path or "").strip() or None
        is_override = not is_github_mode  # Override if not originally github-managed
        
        self._on_task_log(task_id, format_log("gh", "pr", "INFO", f"PR requested ({branch} -> {base_display})"))
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
                is_override,
            ),
            daemon=True,
        ).start()
