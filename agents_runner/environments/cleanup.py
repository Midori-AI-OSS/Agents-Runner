"""
Cleanup and resource management for task workspaces.

Provides utilities to clean up task-specific directories and manage disk space.
"""

import os
import shutil
import time

from datetime import datetime
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable

from midori_ai_logger import MidoriAiLogger

from agents_runner.log_format import format_log
from .paths import managed_repo_checkout_path
from .task_workspaces import finished_cutoff_s
from .task_workspaces import is_safe_task_workspace_path
from .task_workspaces import task_workspace_candidates
from .task_workspaces import task_workspace_path

logger = MidoriAiLogger(channel=None, name=__name__)

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


def cleanup_by_size(
    *,
    threshold_gb: int,
    task_payloads: Iterable[dict[str, Any]],
    active_task_ids: set[str],
    finalizing_task_ids: set[str],
    data_dir: str | None,
    on_log: Callable[[str], None] | None = None,
) -> int:
    """
    Remove oldest finished workspaces until total workspace size falls under threshold.

    Args:
        threshold_gb: Size threshold in GB. Non-positive values make this a no-op.
        task_payloads: Iterable of task payload dicts to evaluate.
        active_task_ids: Set of task IDs currently active (will not be removed).
        finalizing_task_ids: Set of task IDs currently finalizing (will not be removed).
        data_dir: Optional data directory path.
        on_log: Optional callback for logging messages.

    Returns:
        Number of workspaces removed.
    """
    if threshold_gb <= 0:
        return 0

    threshold_bytes = threshold_gb * (1024**3)

    # Filter and deduplicate candidates
    seen: set[tuple[str, str]] = set()
    candidates: list[tuple[float, str, str]] = []

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
        key = (env_id, task_id)
        if key in seen:
            continue
        seen.add(key)

        # Determine sort key (oldest first = smallest timestamp)
        finished_s = _payload_finished_at_s(payload)
        if finished_s is not None:
            ts = finished_s
        else:
            # Fall back to workspace directory st_mtime
            try:
                ws_path = task_workspace_path(env_id, task_id=task_id, data_dir=data_dir)
                ts = os.path.getmtime(ws_path)
            except OSError:
                ts = 0.0

        candidates.append((ts, env_id, task_id))

    if not candidates:
        return 0

    # Sort oldest-first (ascending timestamp)
    candidates.sort(key=lambda x: x[0])

    # Measure current total size
    data_path = Path(data_dir) if data_dir else Path(".")
    total_size = get_workspace_tree_size(data_path)

    if total_size < threshold_bytes:
        return 0

    removed = 0
    for _ts, env_id, task_id in candidates:
        if total_size < threshold_bytes:
            break
        if cleanup_task_workspace(
            env_id=env_id,
            task_id=task_id,
            data_dir=data_dir,
            on_log=on_log,
        ):
            removed += 1
            total_size = get_workspace_tree_size(data_path)

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
        msg = format_log("cleanup", "safety", "WARN", f"Refusing to remove symlink: {task_workspace}")
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
        msg = format_log("cleanup", "task", "INFO", f"Removing task workspace: {task_workspace}")
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
            logger.debug(format_log("cleanup", "task", "DEBUG", f"Error removing {path}: {exc}"))
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

        logger.info(format_log("cleanup", "task", "INFO", f"Successfully removed: {task_workspace}"))
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


def get_workspace_tree_size(root: Path) -> int:
    """
    Recursively calculate the total size (in bytes) of all regular files under
    *root*, skipping directories, symlinks, and special files.

    Args:
        root: Directory path to scan.

    Returns:
        Total number of bytes consumed by regular files under *root*.
    """
    total = 0
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += get_workspace_tree_size(Path(entry.path))
                except (OSError, PermissionError) as exc:
                    logger.warning(
                        format_log(
                            "cleanup",
                            "tree-size",
                            "WARN",
                            f"Skipping unreadable entry {entry.path}: {exc}",
                        )
                    )
    except (OSError, PermissionError) as exc:
        logger.warning(
            format_log(
                "cleanup",
                "tree-size",
                "WARN",
                f"Skipping unreadable directory {root}: {exc}",
            )
        )
    return total
