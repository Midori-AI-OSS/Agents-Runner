import json
import logging
import os

from typing import Any

logger = logging.getLogger(__name__)

from agents_runner.persistence import default_state_path
from agents_runner.persistence import load_state
from agents_runner.persistence import save_state

from .model import ENVIRONMENT_FILENAME_PREFIX
from .model import Environment
from .paths import default_data_dir
from .paths import environment_path
from .serialize import _environment_from_payload
from .serialize import serialize_environment
from .prompt_storage import delete_prompt_file


def _state_path_for_data_dir(data_dir: str) -> str:
    return os.path.join(data_dir, os.path.basename(default_state_path()))


def _load_legacy_environments(data_dir: str) -> dict[str, Environment]:
    if not os.path.isdir(data_dir):
        return {}
    envs: dict[str, Environment] = {}
    for name in sorted(os.listdir(data_dir)):
        if not name.startswith(ENVIRONMENT_FILENAME_PREFIX) or not name.endswith(
            ".json"
        ):
            continue
        path = os.path.join(data_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read legacy environment file {path}: {e}. Skipping this environment.")
            continue
        env = _environment_from_payload(payload)
        if env is None:
            continue
        envs[env.env_id] = env
    return envs


def load_environments(data_dir: str | None = None) -> dict[str, Environment]:
    data_dir = data_dir or default_data_dir()
    state_path = _state_path_for_data_dir(data_dir)
    if not os.path.exists(state_path):
        return {}
    state = load_state(state_path)
    default_max_agents_running = -1
    settings = state.get("settings")
    if isinstance(settings, dict):
        try:
            default_max_agents_running = int(
                str(settings.get("max_agents_running", -1)).strip()
            )
        except Exception as e:
            logger.warning(f"Failed to parse max_agents_running setting: {e}. Using default value of -1.")
            default_max_agents_running = -1
    raw = state.get("environments")
    envs: dict[str, Environment] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            has_max_agents = "max_agents_running" in item
            env = _environment_from_payload(item)
            if env is None:
                continue
            if not has_max_agents:
                env.max_agents_running = default_max_agents_running
            envs[env.env_id] = env
    if envs:
        return envs

    legacy_envs = _load_legacy_environments(data_dir)
    if legacy_envs:
        state = dict(state)
        state["environments"] = [
            serialize_environment(env) for env in legacy_envs.values()
        ]
        save_state(state_path, state)
    return legacy_envs


def save_environment(env: Environment, data_dir: str | None = None) -> None:
    data_dir = data_dir or default_data_dir()
    state_path = _state_path_for_data_dir(data_dir)
    state = load_state(state_path)

    payload = serialize_environment(env)
    env_id = str(payload.get("env_id") or "").strip()
    if not env_id:
        return

    env_map: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    raw = state.get("environments")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            existing_id = str(item.get("env_id") or item.get("id") or "").strip()
            if not existing_id or existing_id in env_map:
                continue
            env_map[existing_id] = dict(item)
            order.append(existing_id)
    env_map[env_id] = payload
    if env_id not in order:
        order.append(env_id)

    state = dict(state)
    state["environments"] = [env_map[item_id] for item_id in order]
    save_state(state_path, state)


def delete_environment(env_id: str, data_dir: str | None = None) -> None:
    data_dir = data_dir or default_data_dir()
    state_path = _state_path_for_data_dir(data_dir)
    state = load_state(state_path)
    
    # Load the environment to get prompt paths before deleting
    raw = state.get("environments")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            existing_id = str(item.get("env_id") or item.get("id") or "").strip()
            if existing_id == str(env_id or "").strip():
                env = _environment_from_payload(item)
                if env:
                    # Delete associated prompt files
                    for prompt in env.prompts or []:
                        if prompt.prompt_path:
                            try:
                                delete_prompt_file(prompt.prompt_path)
                            except Exception as e:
                                # Best-effort cleanup: ignore errors while deleting prompt files.
                                logger.warning(f"Failed to delete prompt file {prompt.prompt_path} for environment {env_id}: {e}")
                break
    
    # Remove from state
    if isinstance(raw, list):
        keep: list[dict[str, Any]] = []
        target = str(env_id or "").strip()
        for item in raw:
            if not isinstance(item, dict):
                continue
            existing_id = str(item.get("env_id") or item.get("id") or "").strip()
            if existing_id and existing_id != target:
                keep.append(item)
        state = dict(state)
        state["environments"] = keep
        save_state(state_path, state)

    path = environment_path(env_id, data_dir=data_dir)
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception as e:
        logger.warning(f"Failed to delete legacy environment file {path}: {e}")
