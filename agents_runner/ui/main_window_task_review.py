from __future__ import annotations

import threading

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.log_format import format_log
from agents_runner.merge_pull_request import build_merge_pull_request_prompt
from agents_runner.ui.task_git_metadata import has_merge_pr_metadata


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
        if not repo_root and env:
            repo_root = str(getattr(env, "host_repo_root", "") or getattr(env, "host_folder", "") or "").strip()
        
        if not branch:
            branch = f"midoriaiagents/{task_id}"
        
        if not repo_root:
            QMessageBox.warning(
                self, "PR not available", "This task is missing repo/branch metadata."
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

    def _on_task_merge_agent_requested(self, task: object) -> None:
        if not has_merge_pr_metadata(task):
            QMessageBox.information(
                self,
                "Merge agent not available",
                "This task is missing saved pull request metadata (base branch, target branch, pull request number).",
            )
            return

        git = getattr(task, "git", None) if task is not None else None
        if not isinstance(git, dict):
            return
        base_branch = str(git.get("base_branch") or "").strip()
        target_branch = str(git.get("target_branch") or "").strip()
        pr_number = git.get("pull_request_number")
        if not (base_branch and target_branch and isinstance(pr_number, int) and pr_number > 0):
            return

        env_id = str(getattr(task, "environment_id", "") or "").strip()
        if not env_id or env_id not in self._environments:
            QMessageBox.warning(
                self,
                "Unknown environment",
                "This task does not have a usable environment ID for starting a merge agent.",
            )
            return

        prompt = build_merge_pull_request_prompt(
            base_branch=base_branch,
            target_branch=target_branch,
            pull_request_number=pr_number,
        )
        host_codex_dir = str(getattr(task, "host_codex_dir", "") or "").strip()

        new_task_id = self._start_task_from_ui(
            prompt,
            host_codex_dir,
            env_id,
            base_branch,
        )
        if not new_task_id:
            return

        new_task = self._tasks.get(new_task_id)
        if new_task is None:
            return

        pr_url = str(git.get("pull_request_url") or getattr(task, "gh_pr_url", "") or "").strip()
        if not pr_url:
            repo_url = str(git.get("repo_url") or "").strip()
            if repo_url:
                pr_url = f"{repo_url.rstrip('/')}/pull/{pr_number}"

        if pr_url:
            new_task.gh_pr_url = pr_url

        new_task.git = {
            **dict(git),
            "task_role": "merge_agent",
            "pull_request_number": pr_number,
            "base_branch": base_branch,
            "target_branch": target_branch,
            "pull_request_url": pr_url,
        }

        self._on_task_log(
            str(getattr(task, "task_id", "") or ""),
            format_log("merge", "agent", "INFO", f"merge agent started: {new_task_id} (pull request #{pr_number})"),
        )
        self._schedule_save()
