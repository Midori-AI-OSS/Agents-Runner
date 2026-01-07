"""Git repository detection and context extraction for environments.

This module provides git detection and context extraction for folder-locked
environments. All operations have 8-second timeouts and never raise exceptions
that would block task execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from agents_runner.gh.git_ops import (
    git_current_branch,
    git_head_commit,
    git_remote_url,
    git_repo_root,
    is_git_repo,
    parse_github_url,
)

logger = logging.getLogger(__name__)


@dataclass
class GitInfo:
    """Git repository context information.
    
    Contains all metadata needed to populate the GitHub context file.
    """
    repo_root: str
    repo_url: str
    repo_owner: str | None
    repo_name: str | None
    branch: str
    commit_sha: str


def get_git_info(path: str) -> Optional[GitInfo]:
    """Detect git repository context for a given path.
    
    This is the main entry point for git detection. It performs all necessary
    checks and extracts repository metadata.
    
    Args:
        path: File system path to check (can be anywhere in a git repo)
        
    Returns:
        GitInfo object if path is in a git repository and all operations succeed,
        None otherwise.
        
    Behavior:
        - All git operations have 8-second timeout
        - Never raises exceptions
        - Returns None on any error
        - Logs warnings for failures
        
    Graceful Degradation:
        - Not a git repo → None
        - No remote configured → None
        - Git command fails → None
        - Can't parse URL → GitInfo with owner=None, repo_name=None
    """
    try:
        # Step 1: Check if git repo
        if not is_git_repo(path):
            logger.debug(f"[gh] path is not a git repository: {path}")
            return None
        
        # Step 2: Get repo root
        repo_root = git_repo_root(path)
        if not repo_root:
            logger.warning(f"[gh] could not determine git repo root: {path}")
            return None
        
        # Step 3: Get current branch
        branch = git_current_branch(repo_root)
        if not branch:
            # Detached HEAD state or error
            logger.warning(f"[gh] could not determine current branch: {repo_root}")
            branch = "HEAD"
        
        # Step 4: Get HEAD commit SHA
        commit_sha = git_head_commit(repo_root)
        if not commit_sha:
            logger.warning(f"[gh] could not get HEAD commit SHA: {repo_root}")
            return None
        
        # Step 5: Get remote URL (try origin first)
        repo_url = git_remote_url(repo_root, remote="origin")
        if not repo_url:
            logger.warning(f"[gh] no remote 'origin' configured: {repo_root}")
            return None
        
        # Step 6: Parse owner/repo from URL (best effort)
        repo_owner, repo_name = parse_github_url(repo_url)
        if not repo_owner or not repo_name:
            logger.debug(
                f"[gh] could not parse owner/repo from URL (non-GitHub?): {repo_url}"
            )
            # Still return GitInfo with raw URL, just no parsed components
        
        return GitInfo(
            repo_root=repo_root,
            repo_url=repo_url,
            repo_owner=repo_owner,
            repo_name=repo_name,
            branch=branch,
            commit_sha=commit_sha,
        )
        
    except Exception as exc:
        # Catch-all to ensure we never raise
        logger.error(f"[gh] unexpected error during git detection: {exc}", exc_info=True)
        return None
