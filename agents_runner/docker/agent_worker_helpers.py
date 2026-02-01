"""Helper functions for agent worker operations."""

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


def needs_cross_agent_gh_token(environment_id: str | None) -> bool:
    """Check if copilot is in the cross-agent allowlist.

    Returns True if any agent in cross_agent_allowlist uses copilot CLI.
    """
    if not environment_id:
        return False

    # Load environment and validate structure
    try:
        environments = load_environments()
        env = environments.get(str(environment_id))
    except Exception:
        return False

    if env is None or not env.cross_agent_allowlist:
        return False

    if env.agent_selection is None or not env.agent_selection.agents:
        return False

    # Build agent_id → agent_cli mapping for quick lookup
    agent_cli_by_id: dict[str, str] = {
        agent.agent_id: agent.agent_cli for agent in env.agent_selection.agents
    }

    # Check each allowlisted agent_id for copilot
    for agent_id in env.cross_agent_allowlist:
        agent_cli = agent_cli_by_id.get(agent_id)
        if agent_cli and normalize_agent(agent_cli) == "copilot":
            return True

    return False


def headless_desktop_prompt_instructions(*, display: str) -> str:
    """Generate prompt instructions for headless desktop usage."""
    display = str(display or "").strip() or ":1"
    return load_prompt(
        "headless_desktop",
        DISPLAY=display,
    )
