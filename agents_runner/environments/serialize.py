from __future__ import annotations

from typing import Any

from .model import ENVIRONMENT_VERSION
from .model import Environment
from .model import normalize_workspace_type
from .model import PromptConfig
from .model import AgentSelection
from .model import AgentInstance
from .prompt_storage import save_prompt_to_file
from .prompt_storage import load_prompt_from_file
from .prompt_storage import delete_prompt_file


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


def _validate_cross_agent_allowlist(
    raw_allowlist: Any, agents: list[AgentInstance]
) -> list[str]:
    """Validate and sanitize cross-agent allowlist.

    Validation rules:
    1. Coerce to list[str], strip empties, de-dupe
    2. If agents list is empty, return empty list
    3. Filter unknown agent_ids (must exist in agents list)
    4. Enforce max 1 allowlisted per agent_cli (keep first occurrence)

    Args:
        raw_allowlist: Raw allowlist data from JSON
        agents: List of AgentInstance objects

    Returns:
        Validated list of agent_ids
    """
    # Coerce to list[str]
    if not isinstance(raw_allowlist, list):
        return []

    allowlist = [str(item).strip() for item in raw_allowlist if str(item).strip()]

    # If no agents configured, return empty list
    if not agents:
        return []

    # Build lookups for validation
    known_ids = {a.agent_id for a in agents}
    cli_to_id: dict[str, str] = {}  # Normalized CLI -> first matching agent_id
    for a in agents:
        normalized_cli = a.agent_cli.strip().lower()
        if normalized_cli not in cli_to_id:
            cli_to_id[normalized_cli] = a.agent_id

    # Filter and deduplicate
    seen_ids: set[str] = set()
    seen_clis: set[str] = set()
    validated: list[str] = []

    for agent_id in allowlist:
        # Skip if not in known agents
        if agent_id not in known_ids:
            continue

        # Skip if already added
        if agent_id in seen_ids:
            continue

        # Find the agent and check CLI uniqueness
        agent = next((a for a in agents if a.agent_id == agent_id), None)
        if not agent:
            continue

        normalized_cli = agent.agent_cli.strip().lower()

        # Enforce max 1 per CLI (keep first occurrence)
        if normalized_cli in seen_clis:
            continue

        validated.append(agent_id)
        seen_ids.add(agent_id)
        seen_clis.add(normalized_cli)

    return validated


def _serialize_prompts(prompts: list[PromptConfig]) -> list[dict[str, Any]]:
    """Serialize prompts, managing external files.

    Handles three cases:
    1. Empty text with existing file -> DELETE the file
    2. Non-empty text -> SAVE/UPDATE the file
    3. Empty text with no file -> No action needed

    Args:
        prompts: List of PromptConfig objects to serialize

    Returns:
        List of serialized prompt dictionaries
    """
    prompts_data = []
    for p in prompts:
        prompt_path = p.prompt_path or ""
        text = p.text or ""

        # Case 1: Text is empty and we have a file -> DELETE the file
        if not text and prompt_path:
            try:
                delete_prompt_file(prompt_path)
            except Exception:
                # File might not exist, or deletion failed
                pass
            prompt_path = ""  # Clear the path reference

        # Case 2: Text exists -> SAVE/UPDATE the file
        elif text:
            try:
                if prompt_path:
                    # Update existing file
                    with open(prompt_path, "w", encoding="utf-8") as f:
                        f.write(text)
                else:
                    # Create new file
                    prompt_path = save_prompt_to_file(text)
            except Exception:
                # If save fails, keep inline text as fallback
                pass

        # Case 3: Empty text with no file -> No action needed

        prompts_data.append(
            {
                "enabled": p.enabled,
                "prompt_path": prompt_path,
                # Keep text inline only if no file exists
                "text": "" if prompt_path else text,
            }
        )

    return prompts_data


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
    agent_cli_args = str(
        payload.get("agent_cli_args") or payload.get("codex_extra_args") or ""
    ).strip()

    try:
        max_agents_running = int(str(payload.get("max_agents_running", -1)).strip())
    except (ValueError, AttributeError):
        max_agents_running = -1

    preflight_enabled = bool(payload.get("preflight_enabled", False))
    preflight_script = str(payload.get("preflight_script") or "")
    headless_desktop_enabled = bool(payload.get("headless_desktop_enabled", False))
    cache_desktop_build = bool(payload.get("cache_desktop_build", False))
    container_caching_enabled = bool(payload.get("container_caching_enabled", False))
    cached_preflight_script = str(payload.get("cached_preflight_script") or "")

    env_vars = payload.get("env_vars", {})
    env_vars = env_vars if isinstance(env_vars, dict) else {}

    extra_mounts = payload.get("extra_mounts", [])
    extra_mounts = extra_mounts if isinstance(extra_mounts, list) else []

    ports = payload.get("ports", [])
    ports = ports if isinstance(ports, list) else []
    ports_unlocked = bool(payload.get("ports_unlocked", False))
    ports_advanced_acknowledged = bool(
        payload.get("ports_advanced_acknowledged", False)
    ) or bool(ports_unlocked)

    gh_management_locked = bool(payload.get("gh_management_locked", False))
    gh_last_base_branch = str(payload.get("gh_last_base_branch") or "").strip()
    gh_use_host_cli = bool(payload.get("gh_use_host_cli", True))

    # Migration: Rename gh_pr_metadata_enabled to gh_context_enabled
    # Check both old and new field names for backward compatibility
    gh_context_enabled = bool(
        payload.get("gh_context_enabled", payload.get("gh_pr_metadata_enabled", False))
    )

    # Migration: workspace_type from gh_management_mode
    # Prefer new key, fallback to old key
    workspace_type = payload.get("workspace_type")
    if not workspace_type and "gh_management_mode" in payload:
        old_mode = payload["gh_management_mode"]
        if old_mode == "github":
            workspace_type = "cloned"
        elif old_mode == "local":
            workspace_type = "mounted"
        else:
            workspace_type = "none"
    else:
        workspace_type = workspace_type or "none"

    # Migration: workspace_target from gh_management_target
    # Prefer new key, fallback to old key for backward compatibility
    workspace_target = str(
        payload.get("workspace_target") or payload.get("gh_management_target") or ""
    ).strip()

    # Normalize using the new function
    workspace_type = normalize_workspace_type(workspace_type)

    try:
        midoriai_template_likelihood = float(
            payload.get("midoriai_template_likelihood", 0.0)
        )
    except (TypeError, ValueError):
        midoriai_template_likelihood = 0.0
    midoriai_template_likelihood = max(0.0, min(1.0, midoriai_template_likelihood))
    midoriai_template_detected = bool(payload.get("midoriai_template_detected", False))
    midoriai_template_detected_path_raw = payload.get("midoriai_template_detected_path")
    midoriai_template_detected_path = (
        str(midoriai_template_detected_path_raw).strip()
        if isinstance(midoriai_template_detected_path_raw, str)
        else ""
    )
    midoriai_template_detected_path = midoriai_template_detected_path or None

    prompts_data = payload.get("prompts", [])
    prompts = []
    if isinstance(prompts_data, list):
        for p in prompts_data:
            if isinstance(p, dict):
                prompt_path = str(p.get("prompt_path", "")).strip()
                text = str(p.get("text", ""))

                # If we have a prompt_path, load from file (migration case)
                if prompt_path:
                    try:
                        text = load_prompt_from_file(prompt_path)
                    except Exception:
                        # If file doesn't exist, keep inline text as fallback
                        pass

                # Migration: If we have inline text but no path, save to file
                if text and not prompt_path:
                    try:
                        prompt_path = save_prompt_to_file(text)
                    except Exception:
                        # If save fails, keep inline text
                        pass

                prompts.append(
                    PromptConfig(
                        enabled=bool(p.get("enabled", False)),
                        text=text,
                        prompt_path=prompt_path,
                    )
                )
    prompts_unlocked = bool(payload.get("prompts_unlocked", False))

    agent_selection_data = payload.get("agent_selection")
    agent_selection = None
    agents: list[AgentInstance] = []
    if isinstance(agent_selection_data, dict):
        selection_mode = str(agent_selection_data.get("selection_mode", "round-robin"))
        pinned_agent_id = str(
            agent_selection_data.get("pinned_agent_id", "") or ""
        ).strip()

        agents_payload = agent_selection_data.get("agents")
        seen_ids: set[str] = set()

        if isinstance(agents_payload, list):
            for raw in agents_payload:
                if not isinstance(raw, dict):
                    continue
                agent_cli = str(raw.get("agent_cli") or "").strip()
                agent_id = str(raw.get("agent_id") or "").strip()
                config_dir = str(raw.get("config_dir") or "").strip()
                cli_flags = str(raw.get("cli_flags") or "").strip()
                if not agent_cli:
                    continue
                unique_id = _unique_agent_id(
                    seen_ids, agent_id, fallback_prefix=agent_cli.lower()
                )
                agents.append(
                    AgentInstance(
                        agent_id=unique_id,
                        agent_cli=agent_cli,
                        config_dir=config_dir,
                        cli_flags=cli_flags,
                    )
                )

        # Legacy format: enabled_agents + agent_config_dirs
        if not agents:
            enabled_agents = agent_selection_data.get("enabled_agents", [])
            if isinstance(enabled_agents, list):
                enabled_agents = [str(a) for a in enabled_agents if str(a).strip()]
            else:
                enabled_agents = []

            agent_config_dirs = agent_selection_data.get("agent_config_dirs", {})
            if isinstance(agent_config_dirs, dict):
                agent_config_dirs = {
                    str(k): str(v) for k, v in agent_config_dirs.items()
                }
            else:
                agent_config_dirs = {}
            normalized_config_dirs = {
                str(k).strip().lower(): str(v) for k, v in agent_config_dirs.items()
            }

            for a in enabled_agents:
                agent_cli = str(a).strip()
                if not agent_cli:
                    continue
                unique_id = _unique_agent_id(
                    seen_ids,
                    agent_cli.strip().lower(),
                    fallback_prefix=agent_cli.strip().lower(),
                )
                agents.append(
                    AgentInstance(
                        agent_id=unique_id,
                        agent_cli=agent_cli,
                        config_dir=str(
                            normalized_config_dirs.get(agent_cli.strip().lower(), "")
                            or ""
                        ).strip(),
                        cli_flags="",
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
                pinned_agent_id=pinned_agent_id,
            )

    # Cross-agent delegation settings
    use_cross_agents = bool(payload.get("use_cross_agents", False))
    cross_agent_allowlist_raw = payload.get("cross_agent_allowlist", [])
    cross_agent_allowlist = _validate_cross_agent_allowlist(
        cross_agent_allowlist_raw, agents
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
        cache_desktop_build=cache_desktop_build,
        container_caching_enabled=container_caching_enabled,
        cached_preflight_script=cached_preflight_script,
        preflight_enabled=preflight_enabled,
        preflight_script=preflight_script,
        env_vars={str(k): str(v) for k, v in env_vars.items() if str(k).strip()},
        extra_mounts=[str(item) for item in extra_mounts if str(item).strip()],
        ports=[str(item) for item in ports if str(item).strip()],
        ports_unlocked=ports_unlocked,
        ports_advanced_acknowledged=ports_advanced_acknowledged,
        gh_management_locked=gh_management_locked,
        workspace_type=workspace_type,
        workspace_target=workspace_target,
        gh_last_base_branch=gh_last_base_branch,
        gh_use_host_cli=gh_use_host_cli,
        gh_context_enabled=gh_context_enabled,  # Use migrated field name
        prompts=prompts,
        prompts_unlocked=prompts_unlocked,
        agent_selection=agent_selection,
        use_cross_agents=use_cross_agents,
        cross_agent_allowlist=cross_agent_allowlist,
        midoriai_template_likelihood=midoriai_template_likelihood,
        midoriai_template_detected=midoriai_template_detected,
        midoriai_template_detected_path=midoriai_template_detected_path,
    )


def serialize_environment(env: Environment) -> dict[str, Any]:
    selection_payload: dict[str, Any] | None = None
    agents_list_for_validation: list[AgentInstance] = []

    if env.agent_selection and env.agent_selection.agents:
        agents_list_for_validation = env.agent_selection.agents
        agents_list = [
            {
                "agent_id": a.agent_id,
                "agent_cli": a.agent_cli,
                "config_dir": a.config_dir,
                "cli_flags": a.cli_flags,
            }
            for a in (env.agent_selection.agents or [])
        ]

        # Legacy fields for backwards compatibility with older builds.
        enabled_agents = [
            str(a.agent_cli or "").strip()
            for a in (env.agent_selection.agents or [])
            if str(a.agent_cli or "").strip()
        ]
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
            "pinned_agent_id": str(
                getattr(env.agent_selection, "pinned_agent_id", "") or ""
            ).strip(),
            "agent_config_dirs": legacy_config_dirs,
            "agent_fallbacks": dict(env.agent_selection.agent_fallbacks),
        }

    # Validate cross-agent allowlist before serializing
    validated_allowlist = _validate_cross_agent_allowlist(
        env.cross_agent_allowlist, agents_list_for_validation
    )

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
        "headless_desktop_enabled": bool(
            getattr(env, "headless_desktop_enabled", False)
        ),
        "cache_desktop_build": bool(getattr(env, "cache_desktop_build", False)),
        "container_caching_enabled": bool(
            getattr(env, "container_caching_enabled", False)
        ),
        "cached_preflight_script": str(
            getattr(env, "cached_preflight_script", "") or ""
        ),
        "preflight_enabled": bool(env.preflight_enabled),
        "preflight_script": env.preflight_script,
        "env_vars": dict(env.env_vars),
        "extra_mounts": list(env.extra_mounts),
        "ports": list(getattr(env, "ports", [])),
        "ports_unlocked": bool(getattr(env, "ports_unlocked", False)),
        "ports_advanced_acknowledged": bool(
            getattr(env, "ports_advanced_acknowledged", False)
        ),
        "gh_management_locked": bool(env.gh_management_locked),
        "workspace_type": env.workspace_type,
        "workspace_target": str(env.workspace_target or "").strip(),
        "gh_last_base_branch": str(
            getattr(env, "gh_last_base_branch", "") or ""
        ).strip(),
        "gh_use_host_cli": bool(env.gh_use_host_cli),
        "gh_context_enabled": bool(env.gh_context_enabled),  # Save with new name
        # Also save with old name for backward compatibility with older builds
        "gh_pr_metadata_enabled": bool(env.gh_context_enabled),
        "midoriai_template_likelihood": float(
            max(0.0, min(1.0, float(getattr(env, "midoriai_template_likelihood", 0.0))))
        ),
        "midoriai_template_detected": bool(
            getattr(env, "midoriai_template_detected", False)
        ),
        "midoriai_template_detected_path": (
            str(getattr(env, "midoriai_template_detected_path", "") or "").strip()
            or None
        ),
        "prompts": _serialize_prompts(env.prompts or []),
        "prompts_unlocked": bool(env.prompts_unlocked),
        "agent_selection": selection_payload,
        "use_cross_agents": bool(getattr(env, "use_cross_agents", False)),
        "cross_agent_allowlist": validated_allowlist,
    }
