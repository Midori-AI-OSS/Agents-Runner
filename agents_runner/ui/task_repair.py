"""Task git metadata repair functionality.

This module provides automatic repair of missing or incomplete git metadata
for git-locked tasks. It attempts multiple strategies to reconstruct metadata
from available sources.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agents_runner.pr_metadata import github_context_host_path
from agents_runner.pr_metadata import load_github_metadata

logger = logging.getLogger(__name__)


def repair_task_git_metadata(
    task: Any,
    *,
    state_path: str,
    environments: dict[str, Any],
) -> tuple[bool, str]:
    """Attempt to repair missing git metadata for a task.
    
    Args:
        task: Task to repair
        state_path: Path to state.json for locating context files
        environments: Environment lookup dict
    
    Returns:
        (success, message) tuple where success=True means full or partial repair
    """
    task_id = getattr(task, "task_id", "unknown")
    
    # Step 1: Check if repair is needed
    is_git_locked = bool(getattr(task, "gh_management_locked", False))
    has_metadata = task.git is not None and isinstance(task.git, dict) and task.git
    
    if not is_git_locked:
        logger.debug(f"[repair] task {task_id}: not git-locked, no repair needed")
        return (True, "not git-locked")
    
    if has_metadata:
        # Check if existing metadata is complete
        base_branch = task.git.get("base_branch")
        if base_branch:
            logger.debug(f"[repair] task {task_id}: metadata already present")
            return (True, "metadata already present")
    
    logger.info(f"[repair] task {task_id}: attempting to repair missing git metadata")
    
    # Step 2: Try GitHub context file (v2)
    success, msg = _repair_from_github_context(task, state_path)
    if success:
        logger.info(f"[repair] task {task_id}: {msg}")
        return (True, msg)
    
    # Step 3: Try task fields using existing derive function
    success, msg = _repair_from_task_fields(task)
    if success:
        logger.info(f"[repair] task {task_id}: {msg}")
        return (True, msg)
    
    # Step 4: Try environment repository
    success, msg = _repair_from_environment(task, environments)
    if success:
        logger.info(f"[repair] task {task_id}: {msg}")
        return (True, msg)
    
    # Step 5: Create partial metadata as fallback
    success, msg = _repair_partial_metadata(task)
    if success:
        logger.warning(f"[repair] task {task_id}: {msg}")
        return (False, msg)
    
    logger.error(f"[repair] task {task_id}: repair failed - no metadata sources available")
    return (False, "no metadata sources available")


def _repair_from_github_context(task: Any, state_path: str) -> tuple[bool, str]:
    """Attempt to repair from GitHub context file (v2)."""
    task_id = getattr(task, "task_id", "unknown")
    
    try:
        data_dir = os.path.dirname(state_path)
        context_path = github_context_host_path(data_dir, task_id)
        
        if not os.path.exists(context_path):
            return (False, "context file not found")
        
        metadata = load_github_metadata(context_path)
        if not metadata or not metadata.github:
            return (False, "context file has no github section")
        
        github = metadata.github
        task.git = {
            "repo_url": github.repo_url,
            "repo_owner": github.repo_owner,
            "repo_name": github.repo_name,
            "base_branch": github.base_branch,
            "target_branch": github.task_branch,
            "head_commit": github.head_commit,
        }
        
        # Add PR info if available from task
        pr_url = str(getattr(task, "gh_pr_url", "") or "").strip()
        if pr_url:
            task.git["pull_request_url"] = pr_url
            from agents_runner.ui.task_git_metadata import _parse_pull_request_number
            pr_number = _parse_pull_request_number(pr_url)
            if pr_number is not None:
                task.git["pull_request_number"] = pr_number
        
        return (True, "repaired from GitHub context file")
        
    except Exception as exc:
        logger.debug(f"[repair] failed to load GitHub context: {exc}")
        return (False, f"context file error: {exc}")


def _repair_from_task_fields(task: Any) -> tuple[bool, str]:
    """Attempt to repair using existing derive function."""
    from agents_runner.ui.task_git_metadata import derive_task_git_metadata
    
    derived = derive_task_git_metadata(task)
    if derived and derived.get("base_branch"):
        task.git = derived
        return (True, "repaired from task fields")
    
    return (False, "task fields incomplete")


def _repair_from_environment(task: Any, environments: dict[str, Any]) -> tuple[bool, str]:
    """Attempt to repair from environment repository."""
    task_id = getattr(task, "task_id", "unknown")
    env_id = getattr(task, "environment_id", "")
    
    env = environments.get(env_id)
    if not env:
        return (False, "environment not found")
    
    # Try to get repository path from environment's host_workdir or task's host_workdir
    repo_path = getattr(env, "host_workdir", None)
    if not repo_path:
        repo_path = getattr(task, "host_workdir", None)
    
    if not repo_path or not os.path.isdir(repo_path):
        return (False, "environment has no accessible repository")
    
    try:
        from agents_runner.environments.git_operations import get_git_info
        
        git_info = get_git_info(repo_path)
        if not git_info:
            return (False, "could not extract git info from repository")
        
        task.git = {
            "repo_url": git_info.repo_url,
            "repo_owner": git_info.repo_owner,
            "repo_name": git_info.repo_name,
            "base_branch": git_info.branch,
            "target_branch": getattr(task, "gh_branch", None) or None,
            "head_commit": git_info.commit_sha,
        }
        
        # Add PR info if available
        pr_url = str(getattr(task, "gh_pr_url", "") or "").strip()
        if pr_url:
            task.git["pull_request_url"] = pr_url
            from agents_runner.ui.task_git_metadata import _parse_pull_request_number
            pr_number = _parse_pull_request_number(pr_url)
            if pr_number is not None:
                task.git["pull_request_number"] = pr_number
        
        return (True, "repaired from environment repository")
        
    except Exception as exc:
        logger.debug(f"[repair] failed to query environment repository: {exc}")
        return (False, f"repository query error: {exc}")



def _repair_partial_metadata(task: Any) -> tuple[bool, str]:
    """Create partial metadata from any available fields."""
    if not task.git:
        task.git = {}
    
    # Try to set base_branch from task field
    if not task.git.get("base_branch"):
        base_fallback = str(getattr(task, "gh_base_branch", "") or "").strip()
        if base_fallback:
            task.git["base_branch"] = base_fallback
        else:
            # Last resort: use "main" as default
            task.git["base_branch"] = "main"
    
    # Try to set target_branch from task field
    if not task.git.get("target_branch"):
        target_fallback = str(getattr(task, "gh_branch", "") or "").strip()
        if target_fallback:
            task.git["target_branch"] = target_fallback
    
    # Try to set PR URL from task field
    if not task.git.get("pull_request_url"):
        pr_url = str(getattr(task, "gh_pr_url", "") or "").strip()
        if pr_url:
            task.git["pull_request_url"] = pr_url
            from agents_runner.ui.task_git_metadata import _parse_pull_request_number
            pr_number = _parse_pull_request_number(pr_url)
            if pr_number is not None:
                task.git["pull_request_number"] = pr_number
    
    # Check if we have at least base_branch
    if task.git.get("base_branch"):
        return (True, "partial metadata created (minimal fields only)")
    
    return (False, "could not create even partial metadata")
