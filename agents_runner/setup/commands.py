"""Setup and configuration commands for agent systems and GitHub auth."""

from __future__ import annotations

import shlex

from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_systems import get_agent_system
from agents_runner.setup import github_setup


def get_setup_command(agent_name: str) -> str | None:
    """Get the interactive setup command for an agent system or setup target.

    This is the command used during first-run setup to authenticate
    the target in a terminal window.

    Args:
        agent_name: Agent system name (codex, claude, copilot, gemini) or "github"

    Returns:
        Shell command string, or None if agent doesn't support setup
    """
    if agent_name == "github":
        return github_setup.get_setup_command()
    agent = normalize_agent(agent_name)
    try:
        return get_agent_system(agent).setup_command()
    except KeyError:
        return None


def get_login_command(agent_name: str) -> str | None:
    """Get the login command for an agent.

    Same as get_setup_command, provided for clarity in per-agent management.

    Args:
        agent_name: Agent system name (codex, claude, copilot, gemini) or "github"

    Returns:
        Shell command string, or None if agent doesn't support login
    """
    return get_setup_command(agent_name)


def get_config_command(agent_name: str) -> str | None:
    """Get the configuration command for an agent.

    This command opens the agent's configuration interface or displays
    configuration information.

    Args:
        agent_name: Agent system name (codex, claude, copilot, gemini) or "github"

    Returns:
        Shell command string, or None if agent doesn't have a config command
    """
    if agent_name == "github":
        return github_setup.get_config_command()
    agent = normalize_agent(agent_name)
    try:
        return get_agent_system(agent).config_command()
    except KeyError:
        return None


def get_verify_command(agent_name: str) -> str:
    """Get the verification command for an agent.

    This command tests that the agent CLI is working.

    Args:
        agent_name: Agent system name (codex, claude, copilot, gemini) or "github"

    Returns:
        Shell command string
    """
    if agent_name == "github":
        return github_setup.get_verify_command()
    agent = normalize_agent(agent_name)
    try:
        argv = get_agent_system(agent).verify_command()
    except KeyError:
        argv = [agent, "--version"]
    return " ".join(shlex.quote(part) for part in argv)
