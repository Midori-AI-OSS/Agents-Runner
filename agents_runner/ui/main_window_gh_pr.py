from __future__ import annotations

import subprocess
import threading

from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.gh_management import GhManagementError
from agents_runner.gh_management import commit_push_and_pr
from agents_runner.gh_management import git_current_branch
from agents_runner.gh_management import git_default_base_branch
from agents_runner.gh_management import git_repo_root
from agents_runner.pr_metadata import load_pr_metadata
from agents_runner.pr_metadata import normalize_pr_title


class _MainWindowGitHubPrMixin:
    def _repo_has_pr_work(self, repo_root: str, base_branch: str) -> bool:
        repo_root = str(repo_root or "").strip()
        if not repo_root:
            return False

        try:
            proc = subprocess.run(
                ["git", "-C", repo_root, "status", "--porcelain"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15.0,
            )
        except Exception:
            return False
        if (proc.stdout or "").strip():
            return True

        base_branch = str(base_branch or "").strip() or (git_default_base_branch(repo_root) or "main")
        for base_ref in (base_branch, f"origin/{base_branch}"):
            try:
                ahead_proc = subprocess.run(
                    ["git", "-C", repo_root, "rev-list", "--count", f"{base_ref}..HEAD"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                )
            except Exception:
                continue
            if ahead_proc.returncode != 0:
                continue
            try:
                ahead = int((ahead_proc.stdout or "").strip() or "0")
            except ValueError:
                continue
            return ahead > 0

        return False

    def _maybe_offer_pr_for_task(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        if task_id in getattr(self, "_pr_offer_task_ids", set()):
            return

        task = self._tasks.get(task_id)
        if task is None or task.is_active():
            return

        env = self._environments.get(task.environment_id)
        if env is None or not bool(getattr(env, "gh_management_locked", False)):
            return
        if normalize_gh_management_mode(task.gh_management_mode) != GH_MANAGEMENT_GITHUB:
            return

        repo_root = str(task.gh_repo_root or "").strip()
        if not repo_root:
            repo_root = str(git_repo_root(task.host_workdir) or "").strip()
        if not repo_root:
            return

        branch = str(task.gh_branch or "").strip()
        if not branch:
            branch = str(git_current_branch(repo_root) or "").strip()
        if not branch:
            return

        base_branch = str(task.gh_base_branch or "").strip() or (git_default_base_branch(repo_root) or "main")

        if not self._repo_has_pr_work(repo_root, base_branch):
            return

        self._pr_offer_task_ids.add(task_id)
        task.gh_repo_root = repo_root
        task.gh_branch = branch
        task.gh_base_branch = base_branch
        self._schedule_save()

        message = (
            f"Create a PR from {branch} -> {base_branch}?\n\n"
            "This will commit and push any local changes."
        )
        if QMessageBox.question(self, "Create pull request?", message) != QMessageBox.StandardButton.Yes:
            return

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

    def _finalize_gh_management_worker(
        self,
        task_id: str,
        repo_root: str,
        branch: str,
        base_branch: str,
        prompt_text: str,
        task_token: str,
        use_gh: bool,
        pr_metadata_path: str | None,
        agent_cli: str,
        agent_cli_args: str,
    ) -> None:
        task_id = str(task_id or "").strip()

        def _log(line: str) -> None:
            try:
                self.host_log.emit(task_id, str(line or ""))
            except Exception:
                pass

        try:
            metadata = load_pr_metadata(pr_metadata_path) if pr_metadata_path else None
            fallback_title = f"Agents Runner task {task_token}".strip()
            if prompt_text.strip():
                fallback_title = (prompt_text.strip().splitlines()[0] or fallback_title).strip()
            title = normalize_pr_title(metadata.title if metadata else "", fallback=fallback_title)

            body = (metadata.body if metadata else "") or ""
            if not body.strip() and prompt_text.strip():
                body = "Task prompt:\n\n" + prompt_text.strip()

            _log(f"[gh] creating PR ({branch} -> {base_branch})")
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
        except (GhManagementError, Exception) as exc:
            _log(f"[gh] ERROR: {exc}")
            return

        if pr_url is None:
            _log("[gh] no changes to push/PR")
            return

        if pr_url.strip():
            _log(f"[gh] PR: {pr_url}")
            try:
                self.host_pr_url.emit(task_id, pr_url)
            except Exception:
                pass
            return

        if use_gh:
            _log("[gh] pushed branch; PR not created")
        else:
            _log("[gh] pushed branch (gh disabled)")

