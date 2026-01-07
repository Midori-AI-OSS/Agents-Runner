import os

from agents_runner.persistence import default_state_path

from .model import ENVIRONMENT_FILENAME_PREFIX


def default_data_dir() -> str:
    return os.path.dirname(default_state_path())


def _safe_env_id(env_id: str) -> str:
    safe = "".join(
        ch for ch in (env_id or "").strip() if ch.isalnum() or ch in {"-", "_"}
    )
    return safe or "default"


def _safe_task_id(task_id: str) -> str:
    """Sanitize task_id for filesystem use."""
    safe = "".join(
        ch for ch in (task_id or "").strip() if ch.isalnum() or ch in {"-", "_"}
    )
    return safe or "default"


def environment_path(env_id: str, data_dir: str | None = None) -> str:
    data_dir = data_dir or default_data_dir()
    return os.path.join(
        data_dir, f"{ENVIRONMENT_FILENAME_PREFIX}{_safe_env_id(env_id)}.json"
    )


def managed_repos_dir(data_dir: str | None = None) -> str:
    data_dir = data_dir or default_data_dir()
    return os.path.join(data_dir, "managed-repos")


def managed_repo_checkout_path(
    env_id: str, data_dir: str | None = None, task_id: str | None = None
) -> str:
    """
    Get the checkout path for a managed repository.

    Args:
        env_id: Environment identifier
        data_dir: Optional data directory path
        task_id: Optional task identifier for task-specific isolation

    Returns:
        Path to the checkout directory:
        - With task_id: managed-repos/{env_id}/tasks/{task_id}/
        - Without task_id: managed-repos/{env_id}/ (backward compatible)
    """
    base = os.path.join(managed_repos_dir(data_dir=data_dir), _safe_env_id(env_id))
    if task_id:
        # Task-specific isolation: managed-repos/{env_id}/tasks/{task_id}/
        return os.path.join(base, "tasks", _safe_task_id(task_id))
    # Fallback for single-task or legacy: managed-repos/{env_id}/
    return base
