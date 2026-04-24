from __future__ import annotations

import logging
import re
from typing import Any

from agents_runner.pr_metadata import load_github_metadata

logger = logging.getLogger(__name__)


def parse_pull_request_number(pull_request_url: str) -> int | None:
    url = str(pull_request_url or "").strip()
    if not url:
        return None
    match = re.search(r"/pull/(?P<num>[0-9]+)(?:/|$)", url)
    if not match:
        return None
    try:
        return int(match.group("num"))
    except Exception:
        return None


def validate_git_metadata(git: dict[str, object] | None) -> tuple[bool, str]:
    """Validate that git metadata contains required fields.

    Args:
        git: Git metadata dictionary to validate

    Returns:
        (is_valid, error_message) tuple
    """
    if not git or not isinstance(git, dict):
        return (False, "git metadata is None or not a dict")

    required_fields = ["base_branch"]
    missing = [field for field in required_fields if not git.get(field)]

    if missing:
        return (False, f"missing required fields: {', '.join(missing)}")

    return (True, "ok")


def derive_task_git_metadata(task: Any) -> dict[str, object] | None:
    """Derive stable git metadata for a task.

    Persisted schema (task JSON `git` object):
      - repo_url: str (optional)
      - repo_owner: str (optional)
      - repo_name: str (optional)
      - base_branch: str (optional)
      - target_branch: str (optional; PR head branch)
      - pull_request_number: int (optional)
      - pull_request_url: str (optional)
      - head_commit: str (optional)

    This function is best-effort and must never raise.
    """
    existing = getattr(task, "git", None)
    metadata: dict[str, object] = dict(existing) if isinstance(existing, dict) else {}

    pr_url = str(getattr(task, "gh_pr_url", "") or "").strip()
    if pr_url:
        metadata["pull_request_url"] = pr_url
        pr_number = parse_pull_request_number(pr_url)
        if pr_number is not None:
            metadata["pull_request_number"] = pr_number

    context_path = str(getattr(task, "gh_context_path", "") or "").strip()
    if context_path:
        try:
            gh_metadata = load_github_metadata(context_path)
        except Exception as exc:
            logger.warning(
                "Failed to read GitHub context file %s: %s", context_path, exc
            )
            gh_metadata = None

        if gh_metadata is not None and gh_metadata.github is not None:
            github = gh_metadata.github
            repo_url = str(getattr(github, "repo_url", "") or "").strip()
            if repo_url:
                metadata["repo_url"] = repo_url
            repo_owner = getattr(github, "repo_owner", None)
            if isinstance(repo_owner, str) and repo_owner.strip():
                metadata["repo_owner"] = repo_owner.strip()
            repo_name = getattr(github, "repo_name", None)
            if isinstance(repo_name, str) and repo_name.strip():
                metadata["repo_name"] = repo_name.strip()

            base_branch = str(getattr(github, "base_branch", "") or "").strip()
            if base_branch:
                metadata["base_branch"] = base_branch

            task_branch = getattr(github, "task_branch", None)
            if isinstance(task_branch, str) and task_branch.strip():
                metadata["target_branch"] = task_branch.strip()

            head_commit = str(getattr(github, "head_commit", "") or "").strip()
            if head_commit:
                metadata["head_commit"] = head_commit

    base_fallback = str(getattr(task, "gh_base_branch", "") or "").strip()
    if base_fallback and not str(metadata.get("base_branch") or "").strip():
        metadata["base_branch"] = base_fallback

    target_fallback = str(getattr(task, "gh_branch", "") or "").strip()
    if target_fallback and not str(metadata.get("target_branch") or "").strip():
        metadata["target_branch"] = target_fallback

    return metadata or None
