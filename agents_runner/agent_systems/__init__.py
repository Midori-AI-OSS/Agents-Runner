"""Agent systems plugin infrastructure."""

from __future__ import annotations

__all__ = [
    "AgentSystemPlugin",
    "AgentSystemPlan",
    "AgentSystemRequest",
    "requires_github_token",
]

from agents_runner.agent_systems.models import (
    AgentSystemPlan,
    AgentSystemPlugin,
    AgentSystemRequest,
)
from agents_runner.agent_systems.registry import get_plugin


def requires_github_token(agent_cli: str) -> bool:
    """Check if an agent system requires GitHub token.

    Args:
        agent_cli: Agent CLI name to check

    Returns:
        True if the agent requires GitHub token, False otherwise
    """
    plugin = get_plugin(agent_cli)
    if plugin is None:
        return False
    return plugin.capabilities.requires_github_token
