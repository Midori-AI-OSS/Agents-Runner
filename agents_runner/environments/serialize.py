from __future__ import annotations

from typing import Any

from .model import ENVIRONMENT_VERSION
from .model import Environment
from .model import normalize_gh_management_mode
from .model import PromptConfig
from .model import AgentSelection


def _environment_from_payload(payload: dict[str, Any]) -> Environment | None:
    """Deserialize environment from JSON payload."""
    if not isinstance(payload, dict):
        return None
    version = int(payload.get("version", ENVIRONMENT_VERSION))
    if version != ENVIRONMENT_VERSION:
        return None

    env_id = str(payload.get("env_id") or payload.get("id") or "").strip()
    if not env_id:
        return None

    name = str(payload.get("name") or env_id).strip()
    color = str(payload.get("color") or "slate").strip().lower()
    host_workdir = str(payload.get("host_workdir") or "").strip()
    host_codex_dir = str(payload.get("host_codex_dir") or "").strip()
    agent_cli_args = str(payload.get("agent_cli_args") or payload.get("codex_extra_args") or "").strip()

    try:
        max_agents_running = int(str(payload.get("max_agents_running", -1)).strip())
    except (ValueError, AttributeError):
        max_agents_running = -1

    preflight_enabled = bool(payload.get("preflight_enabled", False))
    preflight_script = str(payload.get("preflight_script") or "")

    env_vars = payload.get("env_vars", {})
    env_vars = env_vars if isinstance(env_vars, dict) else {}

    extra_mounts = payload.get("extra_mounts", [])
    extra_mounts = extra_mounts if isinstance(extra_mounts, list) else []

    gh_management_mode = normalize_gh_management_mode(str(payload.get("gh_management_mode") or ""))
    gh_management_target = str(payload.get("gh_management_target") or "").strip()
    gh_management_locked = bool(payload.get("gh_management_locked", False))
    gh_use_host_cli = bool(payload.get("gh_use_host_cli", True))
    gh_pr_metadata_enabled = bool(payload.get("gh_pr_metadata_enabled", False))

    prompts_data = payload.get("prompts", [])
    prompts = []
    if isinstance(prompts_data, list):
        for p in prompts_data:
            if isinstance(p, dict):
                prompts.append(PromptConfig(
                    enabled=bool(p.get("enabled", False)),
                    text=str(p.get("text", ""))
                ))
    prompts_unlocked = bool(payload.get("prompts_unlocked", False))

    agent_selection_data = payload.get("agent_selection")
    agent_selection = None
    if isinstance(agent_selection_data, dict):
        enabled_agents = agent_selection_data.get("enabled_agents", [])
        if isinstance(enabled_agents, list):
            enabled_agents = [str(a) for a in enabled_agents if str(a).strip()]
        else:
            enabled_agents = []
        
        if enabled_agents:
            selection_mode = str(agent_selection_data.get("selection_mode", "round-robin"))
            
            agent_config_dirs = agent_selection_data.get("agent_config_dirs", {})
            if isinstance(agent_config_dirs, dict):
                agent_config_dirs = {str(k): str(v) for k, v in agent_config_dirs.items()}
            else:
                agent_config_dirs = {}
            
            agent_selection = AgentSelection(
                enabled_agents=enabled_agents,
                selection_mode=selection_mode,
                agent_config_dirs=agent_config_dirs
            )

    return Environment(
        env_id=env_id,
        name=name or env_id,
        color=color,
        host_workdir=host_workdir,
        host_codex_dir=host_codex_dir,
        agent_cli_args=agent_cli_args,
        max_agents_running=max_agents_running,
        preflight_enabled=preflight_enabled,
        preflight_script=preflight_script,
        env_vars={str(k): str(v) for k, v in env_vars.items() if str(k).strip()},
        extra_mounts=[str(item) for item in extra_mounts if str(item).strip()],
        gh_management_mode=gh_management_mode,
        gh_management_target=gh_management_target,
        gh_management_locked=gh_management_locked,
        gh_use_host_cli=gh_use_host_cli,
        gh_pr_metadata_enabled=gh_pr_metadata_enabled,
        prompts=prompts,
        prompts_unlocked=prompts_unlocked,
        agent_selection=agent_selection,
    )


def serialize_environment(env: Environment) -> dict[str, Any]:
    return {
        "version": ENVIRONMENT_VERSION,
        "env_id": env.env_id,
        "name": env.name,
        "color": env.normalized_color(),
        "host_workdir": env.host_workdir,
        "host_codex_dir": env.host_codex_dir,
        # Stored under a generic key, but we also persist the legacy key for
        # backwards compatibility with older builds.
        "agent_cli_args": env.agent_cli_args,
        "codex_extra_args": env.agent_cli_args,
        "max_agents_running": int(env.max_agents_running),
        "preflight_enabled": bool(env.preflight_enabled),
        "preflight_script": env.preflight_script,
        "env_vars": dict(env.env_vars),
        "extra_mounts": list(env.extra_mounts),
        "gh_management_mode": normalize_gh_management_mode(env.gh_management_mode),
        "gh_management_target": str(env.gh_management_target or "").strip(),
        "gh_management_locked": bool(env.gh_management_locked),
        "gh_use_host_cli": bool(env.gh_use_host_cli),
        "gh_pr_metadata_enabled": bool(env.gh_pr_metadata_enabled),
        "prompts": [{"enabled": p.enabled, "text": p.text} for p in (env.prompts or [])],
        "prompts_unlocked": bool(env.prompts_unlocked),
        "agent_selection": {
            "enabled_agents": env.agent_selection.enabled_agents,
            "selection_mode": env.agent_selection.selection_mode,
            "agent_config_dirs": dict(env.agent_selection.agent_config_dirs),
        } if env.agent_selection else None,
    }

