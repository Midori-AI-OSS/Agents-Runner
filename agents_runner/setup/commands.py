"""Agent-specific setup and configuration commands.

This module provides the command strings used to set up and configure
different AI agent CLIs.
"""

from agents_runner.agent_cli import normalize_agent


# Login commands for each agent
# These commands open interactive authentication flows
AGENT_LOGIN_COMMANDS: dict[str, str | None] = {
    "codex": "codex login; read -p 'Press Enter to close...'",
    "claude": "claude; read -p 'Press Enter to close...'",  # Launches interactive setup
    "copilot": "gh auth login && gh copilot explain 'hello'; read -p 'Press Enter to close...'",
    "gemini": None,  # RESEARCH NEEDED: No known interactive setup command
    "github": "gh auth login; read -p 'Press Enter to close...'",
}


# Configuration commands for each agent
# These open configuration interfaces or files
AGENT_CONFIG_COMMANDS: dict[str, str | None] = {
    "codex": "codex --help; read -p 'Press Enter to close...'",
    "claude": None,  # Open config directory instead
    "copilot": "gh copilot config; read -p 'Press Enter to close...'",
    "gemini": None,  # Open settings.json instead
    "github": "gh config list; read -p 'Press Enter to close...'",
}


def get_setup_command(agent_name: str) -> str | None:
    """Get the interactive setup command for an agent.

    This is the command used during first-run setup to authenticate
    the agent in a terminal window.

    Args:
        agent_name: Agent name (codex, claude, copilot, gemini, github)

    Returns:
        Shell command string, or None if agent doesn't support setup
    """
    agent = normalize_agent(agent_name) if agent_name != "github" else "github"
    return AGENT_LOGIN_COMMANDS.get(agent)


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
    agent = normalize_agent(agent_name) if agent_name != "github" else "github"
    return AGENT_CONFIG_COMMANDS.get(agent)


def get_verify_command(agent_name: str) -> str:
    """Get the verification command for an agent.

    This command tests that the agent CLI is working.

    Args:
        agent_name: Agent name (codex, claude, copilot, gemini, github)

    Returns:
        Shell command string
    """
    agent = normalize_agent(agent_name) if agent_name != "github" else "gh"
    return f"{agent} --version"
