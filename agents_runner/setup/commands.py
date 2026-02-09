"""Agent-specific setup and configuration commands."""

from __future__ import annotations

import shlex

from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_systems import get_agent_system


def get_setup_command(agent_name: str) -> str | None:
    """Get the interactive setup command for an agent.

    This is the command used during first-run setup to authenticate
    the agent in a terminal window.

    Args:
        agent_name: Agent name (codex, claude, copilot, gemini, github)

    Returns:
        Shell command string, or None if agent doesn't support setup
    """
    if agent_name == "github":
        return "gh auth login; read -p 'Press Enter to close...'"
    agent = normalize_agent(agent_name)
    try:
        return get_agent_system(agent).setup_command()
    except KeyError:
        return None


def get_login_command(agent_name: str) -> str | None:
    """Get the login command for an agent.

    Same as get_setup_command, provided for clarity in per-agent management.

    Args:
        agent_name: Agent name (codex, claude, copilot, gemini, github)

    Returns:
        Shell command string, or None if agent doesn't support login
    """
    return get_setup_command(agent_name)


def get_config_command(agent_name: str) -> str | None:
    """Get the configuration command for an agent.

    This command opens the agent's configuration interface or displays
    configuration information.

    Args:
        agent_name: Agent name (codex, claude, copilot, gemini, github)

    Returns:
        Shell command string, or None if agent doesn't have a config command
    """
    if agent_name == "github":
        return "gh config list; read -p 'Press Enter to close...'"
    agent = normalize_agent(agent_name)
    try:
        return get_agent_system(agent).config_command()
    except KeyError:
        return None


def get_verify_command(agent_name: str) -> str:
    """Get the verification command for an agent.

    This command tests that the agent CLI is working.

    Args:
        agent_name: Agent name (codex, claude, copilot, gemini, github)

    Returns:
        Shell command string
    """
    if agent_name == "github":
        return "gh --version"
    agent = normalize_agent(agent_name)
    try:
        argv = get_agent_system(agent).verify_command()
    except KeyError:
        argv = [agent, "--version"]
    return " ".join(shlex.quote(part) for part in argv)
