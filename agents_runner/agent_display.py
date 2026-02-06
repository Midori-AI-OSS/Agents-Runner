"""Agent display name and GitHub URL mappings."""

from __future__ import annotations

from agents_runner.agent_systems.registry import get_plugin


def get_agent_display_name(agent_cli: str) -> str:
    """Get the display name for an agent CLI.

    Args:
        agent_cli: The agent CLI name.

    Returns:
        The display name from the plugin, or the agent_cli as fallback.
    """
    normalized = str(agent_cli or "").strip().lower()
    plugin = get_plugin(normalized)
    if plugin and plugin.display_name:
        return plugin.display_name
    return agent_cli


def get_agent_github_url(agent_cli: str) -> str:
    """Get the GitHub URL for an agent CLI.

    Args:
        agent_cli: The agent CLI name.

    Returns:
        The GitHub URL from the plugin, or empty string as fallback.
    """
    normalized = str(agent_cli or "").strip().lower()
    plugin = get_plugin(normalized)
    if plugin and plugin.github_url:
        return plugin.github_url
    return ""


def format_agent_markdown_link(agent_cli: str) -> str:
    """Format agent as a markdown link.

    Args:
        agent_cli: The agent CLI name.

    Returns:
        A markdown link if GitHub URL is available, otherwise just the display name.
    """
    display_name = get_agent_display_name(agent_cli)
    github_url = get_agent_github_url(agent_cli)
    if github_url:
        return f"[{display_name}]({github_url})"
    return display_name
