from __future__ import annotations

from typing import Any

from .model import ENVIRONMENT_VERSION
from .model import Environment
from .model import normalize_gh_management_mode
from .model import PromptConfig
from .model import AgentSelection
from .model import AgentInstance


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
        # Try to load new format first (agent_instances)
        agent_instances_data = agent_selection_data.get("agent_instances", [])
        agent_instances = []
        
        if isinstance(agent_instances_data, list) and agent_instances_data:
            # New format with agent instances
            for inst_data in agent_instances_data:
                if isinstance(inst_data, dict):
                    instance_id = str(inst_data.get("instance_id", "")).strip()
                    agent_type = str(inst_data.get("agent_type", "")).strip()
                    if instance_id and agent_type:
                        agent_instances.append(AgentInstance(
                            instance_id=instance_id,
                            agent_type=agent_type,
                            config_dir=str(inst_data.get("config_dir", "")).strip(),
                            fallback_instance_id=str(inst_data.get("fallback_instance_id", "")).strip()
                        ))
            
            if agent_instances:
                selection_mode = str(agent_selection_data.get("selection_mode", "round-robin"))
                agent_selection = AgentSelection(
                    agent_instances=agent_instances,
                    selection_mode=selection_mode,
                )
        else:
            # Legacy format with enabled_agents list
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
                
                agent_fallbacks = agent_selection_data.get("agent_fallbacks", {})
                if isinstance(agent_fallbacks, dict):
                    agent_fallbacks = {str(k): str(v) for k, v in agent_fallbacks.items()}
                else:
                    agent_fallbacks = {}
                
                # Convert legacy format to new format
                agent_instances = []
                for i, agent_type in enumerate(enabled_agents):
                    instance_id = f"agent-{agent_type}-{i}"
                    config_dir = agent_config_dirs.get(agent_type, "")
                    fallback_agent_type = agent_fallbacks.get(agent_type, "")
                    fallback_instance_id = ""
                    if fallback_agent_type and fallback_agent_type in enabled_agents:
                        fallback_idx = enabled_agents.index(fallback_agent_type)
                        fallback_instance_id = f"agent-{fallback_agent_type}-{fallback_idx}"
                    
                    agent_instances.append(AgentInstance(
                        instance_id=instance_id,
                        agent_type=agent_type,
                        config_dir=config_dir,
                        fallback_instance_id=fallback_instance_id
                    ))
                
                agent_selection = AgentSelection(
                    agent_instances=agent_instances,
                    selection_mode=selection_mode,
                    # Keep legacy fields for backwards compatibility
                    enabled_agents=enabled_agents,
                    agent_config_dirs=agent_config_dirs,
                    agent_fallbacks=agent_fallbacks
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
            "agent_instances": [
                {
                    "instance_id": inst.instance_id,
                    "agent_type": inst.agent_type,
                    "config_dir": inst.config_dir,
                    "fallback_instance_id": inst.fallback_instance_id,
                }
                for inst in env.agent_selection.agent_instances
            ],
            "selection_mode": env.agent_selection.selection_mode,
        } if env.agent_selection else None,
    }

