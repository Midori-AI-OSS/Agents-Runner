"""Helper functions for agent worker operations."""

import os

from agents_runner.agent_configs.storage import load_agent_configs
from agents_runner.agent_configs.storage import resolve_agent_config
from agents_runner.agent_cli import agent_requires_github_token
from agents_runner.agent_cli import normalize_agent
from agents_runner.environments import load_environments
from agents_runner.prompts import load_prompt


def is_gh_context_enabled(environment_id: str | None) -> bool:
    """Check if GitHub Context is enabled in environment settings.

    Returns True if gh_context_enabled is True in the environment.
    """
    if not environment_id:
        return False

    try:
        environments = load_environments()
        env = environments.get(str(environment_id))
    except Exception:
        return False

    if env is None:
        return False

    return bool(getattr(env, "gh_context_enabled", False))


def needs_cross_agent_gh_token(environment_id: str | None, state_path: str = "") -> bool:
    """Check if any cross-agent allowlisted agent requires a GitHub token."""
    if not environment_id:
        return False

    # Load environment and validate structure
    try:
        data_dir = os.path.dirname(str(state_path or "").strip()) if state_path else None
        environments = load_environments(data_dir=data_dir)
        env = environments.get(str(environment_id))
    except Exception:
        return False

    if env is None or not env.cross_agent_allowlist:
        return False

    if env.agent_selection is None or not env.agent_selection.agents:
        return False

    try:
        agent_configs = {
            str(config.config_id or "").strip(): config
            for config in load_agent_configs(state_path)
            if str(config.config_id or "").strip()
        }
    except Exception:
        agent_configs = {}

    # Build agent_id → agent_cli mapping for quick lookup
    agent_cli_by_id: dict[str, str] = {
        str(agent.agent_id or "").strip(): str(
            getattr(
                resolve_agent_config(
                    str(getattr(agent, "config_id", "") or "").strip(),
                    agent_configs,
                ),
                "agent_cli",
                "",
            )
            or ""
        ).strip()
        for agent in env.agent_selection.agents
        if str(getattr(agent, "agent_id", "") or "").strip()
    }

    # Check each allowlisted agent_id for copilot
    for agent_id in env.cross_agent_allowlist:
        agent_cli = agent_cli_by_id.get(agent_id)
        if agent_cli and agent_requires_github_token(normalize_agent(agent_cli)):
            return True

    return False


def headless_desktop_prompt_instructions(*, display: str) -> str:
    """Generate prompt instructions for headless desktop usage."""
    display = str(display or "").strip() or ":1"
    return load_prompt(
        "headless_desktop",
        DISPLAY=display,
    )
