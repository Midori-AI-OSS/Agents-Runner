from __future__ import annotations

import os
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
from agents_runner.gh.task_plan import RepoPlan, commit_push_and_pr, plan_repo_task, prepare_branch_for_task

__all__ = [
    "GhManagementError",
    "RepoPlan",
    "commit_push_and_pr",
    "ensure_github_clone",
    "prepare_github_repo_for_task",
    "prepare_local_repo_for_task",
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
            _log("[gh] WARNING: found .git/index.lock - another git operation may be in progress")
            _log(f"[gh] If this is a stale lock, remove it: rm {lock_file}")

    _log(f"[gh] cloning {repo} -> {dest_dir}")
    ensure_github_clone(
        repo,
        dest_dir,
        prefer_gh=bool(prefer_gh),
        recreate_if_needed=bool(recreate_if_needed),
    )

    result: dict[str, str] = {"repo_root": "", "base_branch": "", "branch": ""}
    if not is_git_repo(dest_dir):
        _log("[gh] not a git repo; skipping branch/PR")
        return result

    plan = plan_repo_task(
        dest_dir,
        task_id=task_id or "task",
        base_branch=(base_branch or None),
    )
    if plan is None:
        _log("[gh] not a git repo; skipping branch/PR")
        return result

    _log(f"[gh] creating branch {plan.branch} (base {plan.base_branch})")
    resolved_base_branch, branch = prepare_branch_for_task(
        plan.repo_root,
        branch=plan.branch,
        base_branch=plan.base_branch,
    )
    return {"repo_root": plan.repo_root, "base_branch": resolved_base_branch, "branch": branch}


def prepare_local_repo_for_task(
    local_dir: str,
    *,
    task_id: str,
    base_branch: str | None = None,
    on_log: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """Prepare a local git repo for a task (without cloning)."""
    task_id = str(task_id or "").strip()
    local_dir = str(local_dir or "").strip()

    def _log(line: str) -> None:
        if on_log is None:
            return
        on_log(str(line or ""))

    result: dict[str, str] = {"repo_root": "", "base_branch": "", "branch": ""}

    if not local_dir or not os.path.isdir(local_dir):
        _log("[gh] local directory does not exist; skipping")
        return result

    # Check for index.lock
    lock_file = os.path.join(local_dir, ".git", "index.lock")
    if os.path.exists(lock_file):
        _log("[gh] WARNING: found .git/index.lock - another git operation may be in progress")
        _log(f"[gh] If this is a stale lock, remove it: rm {lock_file}")

    if not is_git_repo(local_dir):
        _log("[gh] not a git repo; skipping branch/PR")
        return result

    _log(f"[gh] preparing local git repo: {local_dir}")
    plan = plan_repo_task(
        local_dir,
        task_id=task_id or "task",
        base_branch=(base_branch or None),
    )
    if plan is None:
        _log("[gh] not a git repo; skipping branch/PR")
        return result

    _log(f"[gh] creating branch {plan.branch} (base {plan.base_branch})")
    resolved_base_branch, branch = prepare_branch_for_task(
        plan.repo_root,
        branch=plan.branch,
        base_branch=plan.base_branch,
    )
    return {"repo_root": plan.repo_root, "base_branch": resolved_base_branch, "branch": branch}

