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


def environment_path(env_id: str, data_dir: str | None = None) -> str:
    data_dir = data_dir or default_data_dir()
    return os.path.join(
        data_dir, f"{ENVIRONMENT_FILENAME_PREFIX}{_safe_env_id(env_id)}.json"
    )


def managed_repos_dir(data_dir: str | None = None) -> str:
    data_dir = data_dir or default_data_dir()
    return os.path.join(data_dir, "managed-repos")


def managed_repo_checkout_path(env_id: str, data_dir: str | None = None) -> str:
    return os.path.join(managed_repos_dir(data_dir=data_dir), _safe_env_id(env_id))
