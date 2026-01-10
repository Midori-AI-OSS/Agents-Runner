"""Shell script template builders for task execution."""

from __future__ import annotations

import shlex


def shell_log_statement(scope: str, subscope: str, level: str, message: str) -> str:
    """
    Generate shell echo statement with centralized log format.
    
    This ensures consistency with the Python format_log_line() function.
    Format: [scope/subscope][LEVEL] message
    
    Args:
        scope: Log scope (e.g., host, desktop, docker)
        subscope: Log subscope (e.g., clone, git, vnc)
        level: Log level (INFO, WARN, ERROR, DEBUG)
        message: Log message (will be shell-quoted if needed)
    
    Returns:
        Shell echo statement with proper formatting
    """
    # Normalize level to uppercase
    level = level.upper()
    if level not in ("DEBUG", "INFO", "WARN", "ERROR"):
        level = "INFO"
    
    # Quote the message for shell safety
    quoted_message = shlex.quote(message)
    
    return f'echo "[{scope}/{subscope}][{level}] {quoted_message}"'


def build_git_clone_command(
    *,
    gh_repo: str,
    quoted_repo: str,
    quoted_dest: str,
    prefer_gh_cli: bool,
) -> str:
    """Build git clone command with optional gh CLI fallback."""
    if prefer_gh_cli:
        return (
            f"(command -v gh >/dev/null 2>&1 && gh repo clone {quoted_repo} {quoted_dest}) || "
            f"git clone {quoted_repo} {quoted_dest}"
        )
    return f"git clone {quoted_repo} {quoted_dest}"


def build_git_clone_or_update_snippet(
    *,
    gh_repo: str,
    host_workdir: str,
    quoted_dest: str,
    prefer_gh_cli: bool,
    task_id: str | None = None,
    desired_base: str = "",
    is_locked_env: bool = False,
) -> str:
    """
    Build shell snippet for git clone/update with branch management.

    Args:
        gh_repo: Repository URL or identifier
        host_workdir: Host path to workdir (for display)
        quoted_dest: Shell-quoted destination path
        prefer_gh_cli: Whether to prefer gh CLI over git
        task_id: Optional task ID for branch naming
        desired_base: Optional base branch to checkout
        is_locked_env: If True, updates existing repo instead of cloning
    """
    quoted_repo = shlex.quote(gh_repo)

    parts = [shell_log_statement("host", "clone", "INFO", f"preparing {gh_repo} -> {host_workdir}")]

    if is_locked_env:
        # Locked environment: update existing repo
        update_step = (
            f"if [ -d {quoted_dest}/.git ]; then "
            f"cd {quoted_dest} && "
            f'{shell_log_statement("host", "git", "INFO", "updating locked repo")} && '
            f"git fetch origin; "
            f"else "
            f'{shell_log_statement("host", "clone", "ERROR", f"locked environment requires existing repo at {host_workdir}")}; '
            f"exit 1; "
            f"fi"
        )
        parts.append(update_step)
    else:
        # Non-locked environment: clone or skip if exists
        clone_cmd = build_git_clone_command(
            gh_repo=gh_repo,
            quoted_repo=quoted_repo,
            quoted_dest=quoted_dest,
            prefer_gh_cli=prefer_gh_cli,
        )
        clone_step = (
            f"if [ -d {quoted_dest} ] && [ -d {quoted_dest}/.git ]; then "
            f'{shell_log_statement("host", "clone", "INFO", "repo already exists, skipping clone")}; '
            f"else {clone_cmd} || {{ "
            f'STATUS=$?; {shell_log_statement("host", "clone", "ERROR", "git clone failed (exit $STATUS)")}; '
            f'write_finish "$STATUS"; read -r -p "Press Enter to close..."; exit $STATUS; '
            f"}}; fi"
        )
        parts.append(clone_step)

    # Checkout base branch if specified
    if desired_base:
        quoted_base = shlex.quote(desired_base)
        base_step = (
            f"cd {quoted_dest} && "
            f'{shell_log_statement("host", "git", "INFO", f"checking out base branch {desired_base}")} && '
            f"git fetch origin && "
            f"(git checkout {quoted_base} 2>/dev/null || "
            f"git checkout -b {quoted_base} origin/{quoted_base} 2>/dev/null || "
            f'{shell_log_statement("host", "git", "WARN", f"could not checkout {desired_base}, using default branch")})'
        )
        parts.append(base_step)

    # Create task branch if task_id is provided
    if task_id:
        branch_name = f"agents-runner-{task_id}"
        quoted_branch = shlex.quote(branch_name)
        branch_step = (
            f"cd {quoted_dest} && "
            f'{shell_log_statement("host", "git", "INFO", f"creating task branch {branch_name}")} && '
            f"(git checkout -b {quoted_branch} 2>/dev/null || "
            f"git checkout {quoted_branch} 2>/dev/null || "
            f'{shell_log_statement("host", "git", "WARN", f"could not create branch {branch_name}")})'
        )
        parts.append(branch_step)
        parts.append(shell_log_statement("host", "clone", "INFO", f"ready on branch {branch_name}"))
    else:
        parts.append(shell_log_statement("host", "clone", "INFO", "repo ready"))

    return " ; ".join(parts)
