from __future__ import annotations

from typing import Any

from .model import ENVIRONMENT_VERSION
from .model import Environment
from .model import normalize_gh_management_mode
from .model import PromptConfig
from .model import AgentSelection
from .model import AgentInstance


def _unique_agent_id(existing: set[str], desired: str, *, fallback_prefix: str) -> str:
    base = (desired or "").strip()
    if not base:
        base = fallback_prefix
    base = base.strip()
    if base not in existing:
        existing.add(base)
        return base
    i = 2
    while True:
        candidate = f"{base}-{i}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate
        i += 1


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
    headless_desktop_enabled = bool(payload.get("headless_desktop_enabled", False))

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
        selection_mode = str(agent_selection_data.get("selection_mode", "round-robin"))

        agents_payload = agent_selection_data.get("agents")
        agents: list[AgentInstance] = []
        seen_ids: set[str] = set()

        if isinstance(agents_payload, list):
            for raw in agents_payload:
                if not isinstance(raw, dict):
                    continue
                agent_cli = str(raw.get("agent_cli") or "").strip()
                agent_id = str(raw.get("agent_id") or "").strip()
                config_dir = str(raw.get("config_dir") or "").strip()
                if not agent_cli:
                    continue
                unique_id = _unique_agent_id(seen_ids, agent_id, fallback_prefix=agent_cli.lower())
                agents.append(AgentInstance(agent_id=unique_id, agent_cli=agent_cli, config_dir=config_dir))

        # Legacy format: enabled_agents + agent_config_dirs
        if not agents:
            enabled_agents = agent_selection_data.get("enabled_agents", [])
            if isinstance(enabled_agents, list):
                enabled_agents = [str(a) for a in enabled_agents if str(a).strip()]
            else:
                enabled_agents = []

            agent_config_dirs = agent_selection_data.get("agent_config_dirs", {})
            if isinstance(agent_config_dirs, dict):
                agent_config_dirs = {str(k): str(v) for k, v in agent_config_dirs.items()}
            else:
                agent_config_dirs = {}
            normalized_config_dirs = {str(k).strip().lower(): str(v) for k, v in agent_config_dirs.items()}

            for a in enabled_agents:
                agent_cli = str(a).strip()
                if not agent_cli:
                    continue
                unique_id = _unique_agent_id(seen_ids, agent_cli.strip().lower(), fallback_prefix=agent_cli.strip().lower())
                agents.append(
                    AgentInstance(
                        agent_id=unique_id,
                        agent_cli=agent_cli,
                        config_dir=str(normalized_config_dirs.get(agent_cli.strip().lower(), "") or "").strip(),
                    )
                )

        agent_fallbacks = agent_selection_data.get("agent_fallbacks", {})
        if isinstance(agent_fallbacks, dict):
            agent_fallbacks = {str(k): str(v) for k, v in agent_fallbacks.items()}
        else:
            agent_fallbacks = {}

        # Drop fallbacks pointing to missing agents.
        known_ids = {a.agent_id for a in agents}
        known_by_lower = {a.agent_id.lower(): a.agent_id for a in agents}

        def _resolve_id(value: str) -> str:
            raw = str(value or "").strip()
            if raw in known_ids:
                return raw
            return known_by_lower.get(raw.lower(), "")

        cleaned_fallbacks: dict[str, str] = {}
        for k, v in agent_fallbacks.items():
            kk = _resolve_id(str(k or ""))
            vv = _resolve_id(str(v or ""))
            if kk and vv and kk != vv:
                cleaned_fallbacks[kk] = vv

        if agents:
            agent_selection = AgentSelection(
                agents=agents,
                selection_mode=selection_mode,
                agent_fallbacks=cleaned_fallbacks,
            )

    return Environment(
        env_id=env_id,
        name=name or env_id,
        color=color,
        host_workdir=host_workdir,
        host_codex_dir=host_codex_dir,
        agent_cli_args=agent_cli_args,
        max_agents_running=max_agents_running,
        headless_desktop_enabled=headless_desktop_enabled,
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
    selection_payload: dict[str, Any] | None = None
    if env.agent_selection and env.agent_selection.agents:
        agents_list = [
            {
                "agent_id": a.agent_id,
                "agent_cli": a.agent_cli,
                "config_dir": a.config_dir,
            }
            for a in (env.agent_selection.agents or [])
        ]

        # Legacy fields for backwards compatibility with older builds.
        enabled_agents = [str(a.agent_cli or "").strip() for a in (env.agent_selection.agents or []) if str(a.agent_cli or "").strip()]
        legacy_config_dirs: dict[str, str] = {}
        for a in env.agent_selection.agents or []:
            cli = str(a.agent_cli or "").strip()
            cfg = str(a.config_dir or "").strip()
            if cli and cfg and cli not in legacy_config_dirs:
                legacy_config_dirs[cli] = cfg

        selection_payload = {
            "agents": agents_list,
            "enabled_agents": enabled_agents,
            "selection_mode": env.agent_selection.selection_mode,
            "agent_config_dirs": legacy_config_dirs,
            "agent_fallbacks": dict(env.agent_selection.agent_fallbacks),
        }

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
        "headless_desktop_enabled": bool(getattr(env, "headless_desktop_enabled", False)),
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
        "agent_selection": selection_payload,
    }
