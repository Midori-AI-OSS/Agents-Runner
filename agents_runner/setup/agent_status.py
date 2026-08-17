"""Agent installation and login status detection."""

from __future__ import annotations

from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_agent_system
from agents_runner.agent_systems.github_status import github_auth_status
from agents_runner.agent_systems.status import AgentStatus
from agents_runner.agent_systems.status import StatusType
from agents_runner.agent_systems.status import command_in_path
from agents_runner.agent_systems.status import installed_status
from agents_runner.agent_systems.status import not_installed_status
from agents_runner.gh.auth import get_gh_auth_snapshot


def detect_gh_status() -> AgentStatus:
    """Detect GitHub CLI installation and login status."""

    if not command_in_path("gh"):
        return not_installed_status(agent="github")

    return github_auth_status(agent="github", snapshot=get_gh_auth_snapshot(timeout_s=5.0, use_cache=True))


def detect_all_agents() -> list[AgentStatus]:
    """Detect status for all supported agents and GitHub CLI."""

    statuses: list[AgentStatus] = []
    for agent_name in available_agent_system_names(include_internal=False):
        try:
            plugin = get_agent_system(agent_name)
            statuses.append(plugin.detect_status())
        except Exception:
            statuses.append(
                installed_status(
                    agent=agent_name,
                    logged_in=False,
                    status_text="Unknown (status detection failed)",
                    status_type=StatusType.UNKNOWN,
                )
            )

    statuses.append(detect_gh_status())
    return statuses


__all__ = ["AgentStatus", "StatusType", "detect_all_agents", "detect_gh_status"]
