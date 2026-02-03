from __future__ import annotations

import os
import shutil
from typing import Callable

from agents_runner.gh.errors import GhManagementError
from agents_runner.gh.gh_cli import is_gh_available
from agents_runner.gh.git_ops import (
    git_current_branch,
    git_default_base_branch,
    git_is_clean,
    git_list_branches,
    git_list_remote_heads,
    git_repo_root,
    is_git_repo,
)
from agents_runner.gh.repo_clone import ensure_github_clone
from agents_runner.gh.task_plan import (
    RepoPlan,
    commit_push_and_pr,
    plan_repo_task,
    prepare_branch_for_task,
)
from agents_runner.log_format import format_log

__all__ = [
    "GhManagementError",
    "RepoPlan",
    "commit_push_and_pr",
    "ensure_github_clone",
    "prepare_github_repo_for_task",
    "git_current_branch",
    "git_default_base_branch",
    "git_is_clean",
    "git_list_branches",
    "git_list_remote_heads",
    "git_repo_root",
    "is_gh_available",
    "is_git_repo",
    "plan_repo_task",
    "prepare_branch_for_task",
]


def _delete_checkout_dir(
    dest_dir: str, *, on_log: Callable[[str], None] | None = None
) -> None:
    path = os.path.abspath(os.path.expanduser((dest_dir or "").strip()))
    if not path:
        raise GhManagementError("missing destination directory")
    if path in {os.path.abspath(os.sep), os.path.expanduser("~")}:
        raise GhManagementError(f"refusing to delete unsafe path: {path}")
    if not os.path.isdir(path):
        return
    if on_log is not None:
        on_log(
            format_log("gh", "cleanup", "INFO", f"deleting corrupted checkout: {path}")
        )
    try:
        shutil.rmtree(path)
    except OSError as exc:
        raise GhManagementError(f"failed to delete checkout: {path}\n{exc}") from exc


def prepare_github_repo_for_task(
    repo: str,
    dest_dir: str,
    *,
    task_id: str,
    base_branch: str | None = None,
    prefer_gh: bool = True,
    recreate_if_needed: bool = True,
    on_log: Callable[[str], None] | None = None,
) -> dict[str, str]:
    task_id = str(task_id or "").strip()
    repo = str(repo or "").strip()
    dest_dir = str(dest_dir or "").strip()

    def _log(line: str) -> None:
        if on_log is None:
            return
        on_log(str(line or ""))

    if dest_dir:
        lock_file = os.path.join(dest_dir, ".git", "index.lock")
        if os.path.exists(lock_file):
            import time

            try:
                lock_mtime = os.path.getmtime(lock_file)
                age_seconds = time.time() - lock_mtime
                if age_seconds > 300:  # 5 minutes
                    _log(
                        format_log(
                            "gh",
                            "lock",
                            "INFO",
                            f"Found stale .git/index.lock ({age_seconds:.0f}s old), removing",
                        )
                    )
                    try:
                        os.unlink(lock_file)
                        _log(
                            format_log(
                                "gh",
                                "lock",
                                "INFO",
                                "Stale lock file removed successfully",
                            )
                        )
                    except OSError as rm_exc:
                        _log(
                            format_log(
                                "gh",
                                "lock",
                                "WARN",
                                f"Could not remove stale lock: {rm_exc}",
                            )
                        )
                else:
                    _log(
                        format_log(
                            "gh",
                            "lock",
                            "WARN",
                            "found .git/index.lock - another git operation may be in progress",
                        )
                    )
                    _log(
                        format_log(
                            "gh",
                            "lock",
                            "INFO",
                            f"Lock file age: {age_seconds:.0f}s (will auto-remove after 300s)",
                        )
                    )
            except Exception as exc:
                _log(
                    format_log(
                        "gh", "lock", "ERROR", f"Could not check lock file age: {exc}"
                    )
                )
                _log(
                    format_log(
                        "gh",
                        "lock",
                        "INFO",
                        f"If this is a stale lock, remove it: rm {lock_file}",
                    )
                )

    for attempt in range(2):
        try:
            _log(format_log("gh", "clone", "INFO", f"cloning {repo} -> {dest_dir}"))
            ensure_github_clone(
                repo,
                dest_dir,
                prefer_gh=bool(prefer_gh),
                recreate_if_needed=bool(recreate_if_needed),
            )

            result: dict[str, str] = {"repo_root": "", "base_branch": "", "branch": ""}
            if not is_git_repo(dest_dir):
                _log(
                    format_log(
                        "gh", "repo", "INFO", "not a git repo; skipping branch/PR"
                    )
                )
                return result

            plan = plan_repo_task(
                dest_dir,
                task_id=task_id or "task",
                base_branch=(base_branch or None),
            )
            if plan is None:
                _log(
                    format_log(
                        "gh", "repo", "INFO", "not a git repo; skipping branch/PR"
                    )
                )
                return result

            current_branch = git_current_branch(plan.repo_root)
            if current_branch and current_branch == plan.branch:
                _log(
                    format_log(
                        "gh",
                        "branch",
                        "INFO",
                        f"already on task branch {plan.branch}; skipping branch prep",
                    )
                )
                return {
                    "repo_root": plan.repo_root,
                    "base_branch": plan.base_branch,
                    "branch": current_branch,
                }

            if not git_is_clean(plan.repo_root):
                _log(
                    format_log(
                        "gh",
                        "branch",
                        "WARN",
                        "repo has uncommitted changes; skipping branch prep to avoid data loss",
                    )
                )
                return {
                    "repo_root": plan.repo_root,
                    "base_branch": plan.base_branch,
                    "branch": current_branch or "",
                }

            _log(
                format_log(
                    "gh",
                    "branch",
                    "INFO",
                    f"creating branch {plan.branch} (base {plan.base_branch})",
                )
            )
            resolved_base_branch, branch = prepare_branch_for_task(
                plan.repo_root,
                branch=plan.branch,
                base_branch=plan.base_branch,
            )
            return {
                "repo_root": plan.repo_root,
                "base_branch": resolved_base_branch,
                "branch": branch,
            }
        except GhManagementError as exc:
            if attempt == 0 and recreate_if_needed:
                _log(
                    format_log(
                        "gh",
                        "retry",
                        "WARN",
                        f"repo prep failed; recloning fresh: {exc}",
                    )
                )
                _delete_checkout_dir(dest_dir, on_log=on_log)
                continue
            raise
