import os
import tempfile

from typing import Any

import tomli
import tomli_w

from agents_runner.persistence import STATE_VERSION
from agents_runner.persistence import strip_none_for_toml

from .model import AgentConfig


def _load_state_payload(state_path: str) -> dict[str, Any]:
    path = str(state_path or "").strip()
    if not path or not os.path.exists(path):
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    try:
        with open(path, "rb") as f:
            payload = tomli.load(f)
    except Exception:
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    if not isinstance(payload, dict):
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    version = payload.get("version")
    if version != STATE_VERSION:
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    payload.setdefault("version", STATE_VERSION)
    payload.setdefault("tasks", [])
    payload.setdefault("settings", {})
    payload.setdefault("environments", [])
    if not isinstance(payload["tasks"], list):
        payload["tasks"] = []
    if not isinstance(payload["settings"], dict):
        payload["settings"] = {}
    if not isinstance(payload["environments"], list):
        payload["environments"] = []
    return payload


def _atomic_write_state_payload(state_path: str, payload: dict[str, Any]) -> None:
    path = str(state_path or "").strip()
    if not path:
        return
    base_dir = os.path.dirname(path) or os.getcwd()
    os.makedirs(base_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix="state-", suffix=".toml", dir=base_dir)
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(strip_none_for_toml(payload), f)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _as_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {str(k): v for k, v in value.items()}


def load_agent_configs(state_path: str) -> list[AgentConfig]:
    payload = _load_state_payload(state_path)
    raw = payload.get("agent_configs")
    if not isinstance(raw, list):
        return []

    configs: list[AgentConfig] = []
    for item in raw:
        item_dict = _as_dict(item)
        if item_dict is None:
            continue
        config_id = str(item_dict.get("config_id") or "").strip()
        if not config_id:
            continue
        configs.append(
            AgentConfig(
                config_id=config_id,
                agent_cli=str(item_dict.get("agent_cli") or "").strip(),
                config_dir=str(item_dict.get("config_dir") or "").strip(),
                cli_flags=str(item_dict.get("cli_flags") or "").strip(),
            )
        )
    return configs


def resolve_agent_config(
    config_id: str, agent_configs: dict[str, AgentConfig]
) -> AgentConfig | None:
    """Look up an AgentConfig by config_id.

    Returns ``None`` when ``config_id`` is empty or missing from ``agent_configs``.
    """

    target = str(config_id or "").strip()
    if not target:
        return None
    config = agent_configs.get(target)
    if not isinstance(config, AgentConfig):
        return None
    return config


def save_agent_config(state_path: str, config: AgentConfig) -> None:
    config_id = str(getattr(config, "config_id", "") or "").strip()
    if not config_id:
        return

    payload = _load_state_payload(state_path)
    raw_configs = payload.get("agent_configs")
    items: list[dict[str, Any]] = []
    if isinstance(raw_configs, list):
        for item in raw_configs:
            item_dict = _as_dict(item)
            if item_dict is None:
                continue
            existing_id = str(item_dict.get("config_id") or "").strip()
            if not existing_id or existing_id == config_id:
                continue
            items.append(dict(item_dict))

    items.append(
        {
            "config_id": config_id,
            "agent_cli": str(getattr(config, "agent_cli", "") or "").strip(),
            "config_dir": str(getattr(config, "config_dir", "") or "").strip(),
            "cli_flags": str(getattr(config, "cli_flags", "") or "").strip(),
        }
    )
    payload["agent_configs"] = items
    _atomic_write_state_payload(state_path, payload)


def delete_agent_config(state_path: str, config_id: str) -> None:
    target = str(config_id or "").strip()
    if not target:
        return

    payload = _load_state_payload(state_path)
    raw_configs = payload.get("agent_configs")
    if not isinstance(raw_configs, list) or not raw_configs:
        return

    keep: list[dict[str, Any]] = []
    for item in raw_configs:
        item_dict = _as_dict(item)
        if item_dict is None:
            continue
        existing_id = str(item_dict.get("config_id") or "").strip()
        if existing_id and existing_id != target:
            keep.append(dict(item_dict))

    payload["agent_configs"] = keep
    _atomic_write_state_payload(state_path, payload)


def find_envs_referencing_config(state_path: str, config_id: str) -> list[str]:
    target = str(config_id or "").strip()
    if not target:
        return []

    path = str(state_path or "").strip()
    if not path:
        return []

    from agents_runner.environments.storage import load_environments

    data_dir = os.path.dirname(path) or os.getcwd()
    envs = load_environments(data_dir)
    referenced: list[str] = []
    seen: set[str] = set()

    for env in envs.values():
        env_id = str(getattr(env, "env_id", "") or "").strip()
        if not env_id or env_id in seen:
            continue

        selection = getattr(env, "agent_selection", None)
        agents = selection.agents if selection is not None else []
        if any(
            str(getattr(agent, "config_id", "") or "").strip() == target
            for agent in agents
        ):
            referenced.append(env_id)
            seen.add(env_id)

    return referenced
