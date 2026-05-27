"""
Cleanup and resource management for task workspaces.

Provides utilities to clean up task-specific directories and manage disk space.
"""

import logging
import os
import shutil
import time

from datetime import datetime
from collections.abc import Iterable
from typing import Any, Callable

from agents_runner.log_format import format_log
from .paths import managed_repo_checkout_path
from .task_workspaces import finished_cutoff_s
from .task_workspaces import is_safe_task_workspace_path
from .task_workspaces import task_workspace_candidates

logger = logging.getLogger(__name__)

_FINISHED_STATUSES = {"done", "failed", "error", "cancelled", "killed"}


def _timestamp_from_iso(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return float(datetime.fromisoformat(text).timestamp())
    except Exception:
        return None


def _payload_finished_at_s(payload: dict[str, Any]) -> float | None:
    finished = _timestamp_from_iso(payload.get("finished_at"))
    if finished is not None:
        return finished
    try:
        created = float(payload.get("created_at_s") or 0.0)
    except Exception:
        created = 0.0
    return created if created > 0.0 else None


def cleanup_retained_task_workspaces(
    task_payloads: Iterable[dict[str, Any]],
    *,
    data_dir: str | None,
    retention_days: int,
    scan_delay_seconds: int,
    active_task_ids: set[str],
    finalizing_task_ids: set[str],
    on_log: Callable[[str], None] | None = None,
) -> int:
    cutoff_s = finished_cutoff_s(retention_days=retention_days)
    removed = 0
    seen: set[tuple[str, str]] = set()
    for payload in task_payloads:
        task_id = str(payload.get("task_id") or "").strip()
        env_id = str(payload.get("environment_id") or "").strip()
        if not task_id or not env_id:
            continue
        if task_id in active_task_ids or task_id in finalizing_task_ids:
            continue
        if str(payload.get("workspace_type") or "").strip() != "cloned":
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status not in _FINISHED_STATUSES:
            continue
        finished_s = _payload_finished_at_s(payload)
        if finished_s is None or finished_s > cutoff_s:
            continue
        key = (env_id, task_id)
        if key in seen:
            continue
        seen.add(key)
        if cleanup_task_workspace(
            env_id=env_id,
            task_id=task_id,
            data_dir=data_dir,
            on_log=on_log,
        ):
            removed += 1
        if scan_delay_seconds > 0:
            time.sleep(float(scan_delay_seconds))
    return removed


def cleanup_task_workspace(
    env_id: str,
    task_id: str,
    data_dir: str | None = None,
    on_log: Callable[[str], None] | None = None,
    workspace_location: object | None = None,
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
    primary = managed_repo_checkout_path(
        env_id=env_id,
        task_id=task_id,
        data_dir=data_dir,
        workspace_location=workspace_location or "app_data",
    )
    candidates = [primary]
    for candidate in task_workspace_candidates(env_id, task_id, data_dir=data_dir):
        if candidate not in candidates:
            candidates.append(candidate)

    found = False
    success = True
    for task_workspace in candidates:
        if not os.path.exists(task_workspace):
            continue
        found = True
        if not _cleanup_one_task_workspace(
            task_workspace=task_workspace,
            data_dir=data_dir,
            on_log=on_log,
        ):
            success = False

    if not found:
        logger.debug(
            format_log(
                "cleanup",
                "task",
                "DEBUG",
                f"Task workspace already removed: {primary}",
            )
        )
    return success


def _cleanup_one_task_workspace(
    *,
    task_workspace: str,
    data_dir: str | None,
    on_log: Callable[[str], None] | None,
) -> bool:

    # Safety check: reject symlinks to prevent symlink attacks
    if os.path.islink(task_workspace):
        msg = format_log(
            "cleanup", "safety", "WARN", f"Refusing to remove symlink: {task_workspace}"
        )
        logger.warning(msg)
        if on_log:
            on_log(msg)
        return False

    if not is_safe_task_workspace_path(task_workspace, data_dir=data_dir):
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
            exc: BaseException,
        ) -> None:
            """Handle permission errors during removal."""
            logger.debug(
                format_log("cleanup", "task", "DEBUG", f"Error removing {path}: {exc}")
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

        shutil.rmtree(task_workspace, onexc=handle_remove_error)

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
