import json
import os
import tempfile

from typing import Any

from agents_runner.persistence import default_state_path

from .model import Environment
from .paths import default_data_dir
from .serialize import environment_from_payload
from .serialize import serialize_environment
from .prompt_storage import delete_prompt_file


ENVIRONMENTS_FILENAME = "environments.json"


def _state_path_for_data_dir(data_dir: str) -> str:
    return os.path.join(data_dir, os.path.basename(default_state_path()))


def _environments_path_for_data_dir(data_dir: str) -> str:
    state_path = _state_path_for_data_dir(data_dir)
    base_dir = os.path.dirname(state_path) or data_dir or os.getcwd()
    return os.path.join(base_dir, ENVIRONMENTS_FILENAME)


def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f"{os.path.basename(path)}.",
        suffix=".tmp",
        dir=os.path.dirname(path),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _load_environments_items(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return []

    raw: object
    if isinstance(payload, dict):
        payload_dict: dict[str, Any] = payload
        raw = payload_dict.get("environments")
    elif isinstance(payload, list):
        raw = payload
    else:
        return []

    if not isinstance(raw, list):
        return []

    raw_list: list[Any] = raw
    items: list[dict[str, Any]] = []
    for item in raw_list:
        if isinstance(item, dict):
            items.append(item)
    return items


def load_environments(data_dir: str | None = None) -> dict[str, Environment]:
    data_dir = data_dir or default_data_dir()
    envs_path = _environments_path_for_data_dir(data_dir)
    raw = _load_environments_items(envs_path)
    envs: dict[str, Environment] = {}
    for item in raw:
        env = environment_from_payload(item)
        if env is None:
            continue
        envs[env.env_id] = env
    return envs


def save_environment(env: Environment, data_dir: str | None = None) -> None:
    data_dir = data_dir or default_data_dir()
    envs_path = _environments_path_for_data_dir(data_dir)

    payload = serialize_environment(env)
    env_id = str(payload.get("env_id") or "").strip()
    if not env_id:
        return

    env_map: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    raw = _load_environments_items(envs_path)
    for item in raw:
        existing_id = str(item.get("env_id") or item.get("id") or "").strip()
        if not existing_id or existing_id in env_map:
            continue
        env_map[existing_id] = dict(item)
        order.append(existing_id)
    env_map[env_id] = payload
    if env_id not in order:
        order.append(env_id)

    _atomic_write_json(
        envs_path, {"environments": [env_map[item_id] for item_id in order]}
    )


def delete_environment(env_id: str, data_dir: str | None = None) -> None:
    data_dir = data_dir or default_data_dir()
    envs_path = _environments_path_for_data_dir(data_dir)

    raw = _load_environments_items(envs_path)
    if not raw:
        return

    target = str(env_id or "").strip()
    if not target:
        return

    keep: list[dict[str, Any]] = []
    removed: dict[str, Any] | None = None
    for item in raw:
        existing_id = str(item.get("env_id") or item.get("id") or "").strip()
        if existing_id == target and removed is None:
            removed = item
            continue
        keep.append(item)

    if removed is not None:
        env = environment_from_payload(removed)
        if env:
            for prompt in env.prompts or []:
                if prompt.prompt_path:
                    try:
                        delete_prompt_file(prompt.prompt_path)
                    except Exception:
                        # Best-effort cleanup: ignore errors while deleting prompt files.
                        pass

        _atomic_write_json(envs_path, {"environments": keep})
