"""
Cleanup and resource management for task workspaces.

Provides utilities to clean up task-specific directories and manage disk space.
"""

import logging
import os
import shutil
import time
import types
from typing import Any, Callable

from agents_runner.log_format import format_log
from .paths import managed_repo_checkout_path

logger = logging.getLogger(__name__)


def cleanup_task_workspace(
    env_id: str,
    task_id: str,
    data_dir: str | None = None,
    on_log: Callable[[str], None] | None = None,
) -> bool:
    """
    Remove the task-specific workspace directory.

    Args:
        env_id: Environment identifier
        task_id: Task identifier
        data_dir: Optional data directory path (defaults to standard location)
        on_log: Optional callback for logging messages

    Returns:
        True if cleanup succeeded or directory didn't exist, False on error
    """
    task_workspace = managed_repo_checkout_path(
        env_id=env_id, task_id=task_id, data_dir=data_dir
    )

    # Safety check: reject symlinks to prevent symlink attacks
    if os.path.islink(task_workspace):
        msg = format_log(
            "cleanup", "safety", "WARN", f"Refusing to remove symlink: {task_workspace}"
        )
        logger.warning(msg)
        if on_log:
            on_log(msg)
        return False

    # Safety check: ensure we're removing a task-specific directory
    if "/tasks/" not in task_workspace:
        msg = format_log(
            "cleanup",
            "safety",
            "WARN",
            f"Refusing to remove non-task directory: {task_workspace}",
        )
        logger.warning(msg)
        if on_log:
            on_log(msg)
        return False

    if not os.path.exists(task_workspace):
        logger.debug(
            format_log(
                "cleanup",
                "task",
                "DEBUG",
                f"Task workspace already removed: {task_workspace}",
            )
        )
        return True

    try:
        msg = format_log(
            "cleanup", "task", "INFO", f"Removing task workspace: {task_workspace}"
        )
        logger.info(msg)
        if on_log:
            on_log(msg)

        # Use shutil.rmtree with error handler for better cleanup
        def handle_remove_error(
            func: Callable[..., Any],
            path: str,
            exc_info: tuple[type[BaseException], BaseException, types.TracebackType],
        ) -> None:
            """Handle permission errors during removal."""
            logger.debug(
                format_log(
                    "cleanup", "task", "DEBUG", f"Error removing {path}: {exc_info[1]}"
                )
            )
            # Try to make writable and retry
            try:
                os.chmod(path, 0o700)
                func(path)
            except Exception as retry_exc:
                logger.debug(
                    format_log(
                        "cleanup",
                        "task",
                        "DEBUG",
                        f"Retry failed for {path}: {retry_exc}",
                    )
                )

        shutil.rmtree(task_workspace, onerror=handle_remove_error)

        logger.info(
            format_log(
                "cleanup", "task", "INFO", f"Successfully removed: {task_workspace}"
            )
        )
        if on_log:
            on_log(format_log("cleanup", "task", "INFO", "Workspace cleaned up"))
        return True

    except Exception as exc:
        msg = format_log(
            "cleanup",
            "task",
            "ERROR",
            f"Failed to remove task workspace {task_workspace}: {exc}",
        )
        logger.error(msg)
        if on_log:
            on_log(msg)
        return False


def cleanup_old_task_workspaces(
    env_id: str,
    max_age_hours: int = 24,
    data_dir: str | None = None,
    on_log: Callable[[str], None] | None = None,
) -> int:
    """
    Find and remove task directories older than max_age_hours.

    Args:
        env_id: Environment identifier
        max_age_hours: Maximum age in hours (default: 24)
        data_dir: Optional data directory path
        on_log: Optional callback for logging messages

    Returns:
        Number of directories removed
    """
    # Get the tasks directory for this environment
    base_path = managed_repo_checkout_path(env_id=env_id, data_dir=data_dir)
    tasks_dir = os.path.join(base_path, "tasks")

    if not os.path.isdir(tasks_dir):
        logger.debug(
            format_log(
                "cleanup", "scan", "DEBUG", f"No tasks directory found: {tasks_dir}"
            )
        )
        return 0

    max_age_seconds = max_age_hours * 3600
    current_time = time.time()
    removed_count = 0

    try:
        for task_id in os.listdir(tasks_dir):
            task_path = os.path.join(tasks_dir, task_id)

            # Skip if not a directory
            if not os.path.isdir(task_path):
                continue

            try:
                # Check modification time
                mtime = os.path.getmtime(task_path)
                age_seconds = current_time - mtime

                if age_seconds > max_age_seconds:
                    age_hours = age_seconds / 3600
                    logger.info(
                        format_log(
                            "cleanup",
                            "old",
                            "INFO",
                            f"Removing old task workspace (age: {age_hours:.1f}h): {task_path}",
                        )
                    )
                    if on_log:
                        on_log(
                            format_log(
                                "cleanup",
                                "old",
                                "INFO",
                                f"Removing old task {task_id} (age: {age_hours:.1f}h)",
                            )
                        )

                    shutil.rmtree(task_path, ignore_errors=True)
                    removed_count += 1

            except Exception as exc:
                logger.warning(
                    format_log(
                        "cleanup", "old", "WARN", f"Error processing {task_path}: {exc}"
                    )
                )
                continue

        if removed_count > 0:
            msg = format_log(
                "cleanup",
                "old",
                "INFO",
                f"Removed {removed_count} old task workspace(s)",
            )
            logger.info(msg)
            if on_log:
                on_log(msg)

        return removed_count

    except Exception as exc:
        msg = format_log(
            "cleanup",
            "scan",
            "ERROR",
            f"Error scanning tasks directory {tasks_dir}: {exc}",
        )
        logger.error(msg)
        if on_log:
            on_log(msg)
        return removed_count


def get_task_workspace_size(
    env_id: str,
    task_id: str,
    data_dir: str | None = None,
) -> int:
    """
    Get the size in bytes of a task workspace.

    Args:
        env_id: Environment identifier
        task_id: Task identifier
        data_dir: Optional data directory path

    Returns:
        Size in bytes, or 0 if directory doesn't exist or on error
    """
    task_workspace = managed_repo_checkout_path(
        env_id=env_id, task_id=task_id, data_dir=data_dir
    )

    if not os.path.exists(task_workspace):
        return 0

    try:
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(task_workspace):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    # Skip files that we can't access
                    continue
        return total_size

    except Exception as exc:
        logger.warning(
            format_log(
                "cleanup",
                "size",
                "WARN",
                f"Error calculating size for {task_workspace}: {exc}",
            )
        )
        return 0


def cleanup_on_task_completion(
    task_id: str,
    env_id: str,
    data_dir: str | None = None,
    keep_on_error: bool = True,
    on_log: Callable[[str], None] | None = None,
) -> bool:
    """
    Clean up task workspace on task completion.

    This is a convenience wrapper around cleanup_task_workspace that
    implements the policy for when to clean up (e.g., keep failed tasks).

    Args:
        task_id: Task identifier
        env_id: Environment identifier
        data_dir: Optional data directory path
        keep_on_error: If True, don't clean up failed/error tasks (for debugging)
        on_log: Optional callback for logging messages

    Returns:
        True if cleanup succeeded or was skipped, False on error
    """
    if keep_on_error:
        logger.debug(
            format_log(
                "cleanup",
                "policy",
                "DEBUG",
                f"Skipping cleanup for failed task {task_id} (keep_on_error=True)",
            )
        )
        if on_log:
            on_log(
                format_log(
                    "cleanup", "policy", "INFO", "Keeping workspace for debugging"
                )
            )
        return True

    return cleanup_task_workspace(
        env_id=env_id, task_id=task_id, data_dir=data_dir, on_log=on_log
    )
