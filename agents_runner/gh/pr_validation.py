"""Pre-flight validation for pull request creation.

This module provides validation checks that must pass before attempting
to create a pull request. All validations are designed to fail fast and
provide clear, actionable error messages.
"""

from __future__ import annotations

import os
import subprocess


def validate_pr_prerequisites(
    *,
    repo_root: str,
    branch: str,
    use_gh: bool = True,
) -> list[tuple[str, bool, str]]:
    """Run all pre-flight validation checks for PR creation.

    Args:
        repo_root: Path to git repository root
        branch: Target branch name for PR
        use_gh: Whether gh CLI will be used for PR creation

    Returns:
        List of (check_name, passed, message) tuples
    """
    checks: list[tuple[str, bool, str]] = []

    # Check 1: Git repository exists
    passed, msg = _validate_git_repo(repo_root)
    checks.append(("git_repo", passed, msg))
    if not passed:
        return checks  # Can't continue without valid repo

    # Check 2: Remote is configured
    passed, msg = _validate_remote(repo_root)
    checks.append(("remote", passed, msg))

    # Check 3: GitHub CLI (if needed)
    passed, msg = _validate_gh_cli(use_gh)
    checks.append(("gh_cli", passed, msg))

    # Check 4: Check for existing PR (informational, not a failure)
    existing_pr = check_existing_pr(repo_root, branch)
    if existing_pr:
        checks.append(("existing_pr", True, f"PR already exists: {existing_pr}"))
    else:
        checks.append(("existing_pr", True, "no existing PR found"))

    return checks


def _validate_git_repo(repo_root: str) -> tuple[bool, str]:
    """Verify path is a valid git repository."""
    if not os.path.isdir(repo_root):
        return (False, "repository path does not exist")

    if not os.path.isdir(os.path.join(repo_root, ".git")):
        return (False, "not a git repository (no .git folder)")

    # Test git command works
    try:
        result = subprocess.run(
            ["git", "-C", repo_root, "status"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if result.returncode != 0:
            return (False, f"git command failed: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        return (False, "git command timed out")
    except Exception as exc:
        return (False, f"git command error: {exc}")

    return (True, "ok")


def _validate_remote(repo_root: str) -> tuple[bool, str]:
    """Verify origin remote is configured."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_root, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if result.returncode != 0:
            return (False, "no origin remote configured")

        remote_url = result.stdout.strip()
        if not remote_url:
            return (False, "origin remote URL is empty")

        return (True, f"remote: {remote_url}")
    except subprocess.TimeoutExpired:
        return (False, "git remote command timed out")
    except Exception as exc:
        return (False, f"git remote check failed: {exc}")


def _validate_gh_cli(use_gh: bool) -> tuple[bool, str]:
    """Verify gh CLI is available and authenticated."""
    if not use_gh:
        return (True, "gh CLI disabled")

    # Check if gh is installed
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if result.returncode != 0:
            return (False, "gh CLI not installed")
    except FileNotFoundError:
        return (False, "gh CLI not found in PATH")
    except subprocess.TimeoutExpired:
        return (False, "gh CLI version check timed out")
    except Exception as exc:
        return (False, f"gh CLI check failed: {exc}")

    # Check authentication
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if result.returncode != 0:
            return (False, "gh CLI not authenticated (run 'gh auth login')")
    except subprocess.TimeoutExpired:
        return (False, "gh auth status check timed out")
    except Exception as exc:
        return (False, f"gh auth check failed: {exc}")

    return (True, "gh CLI ready")


def check_existing_pr(repo_root: str, branch: str) -> str | None:
    """Check if PR already exists for branch. Returns PR URL or None."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--json", "url", "--jq", ".[0].url"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15.0,
        )

        if result.returncode == 0 and result.stdout:
            url = result.stdout.strip()
            if url.startswith("http"):
                return url
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        # If we can't check, assume no PR exists
        pass

    return None
