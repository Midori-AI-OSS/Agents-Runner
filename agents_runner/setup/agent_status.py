"""Agent installation and login status detection."""

from __future__ import annotations

import subprocess

from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_agent_system
from agents_runner.agent_systems.status import AgentStatus
from agents_runner.agent_systems.status import StatusType
from agents_runner.agent_systems.status import command_in_path
from agents_runner.agent_systems.status import installed_status
from agents_runner.agent_systems.status import not_installed_status


def detect_gh_status() -> AgentStatus:
    """Detect GitHub CLI installation and login status."""

    if not command_in_path("gh"):
        return not_installed_status(agent="github")

    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return installed_status(
            agent="github",
            logged_in=False,
            status_text="Unknown (timeout)",
            status_type=StatusType.UNKNOWN,
        )
    except (FileNotFoundError, OSError):
        return installed_status(
            agent="github",
            logged_in=False,
            status_text="Unknown (gh CLI not found)",
            status_type=StatusType.UNKNOWN,
        )

    if result.returncode == 0 and "Logged in" in result.stdout:
        username = None
        for line in result.stdout.split("\n"):
            if "Logged in to github.com account" not in line:
                continue
            parts = line.split("account")
            if len(parts) > 1:
                username = parts[1].split("(")[0].strip() or None
                break
        if username:
            return installed_status(
                agent="github",
                logged_in=True,
                status_text=f"Logged in as {username}",
                username=username,
            )
        return installed_status(
            agent="github",
            logged_in=True,
            status_text="Logged in",
        )

    return installed_status(
        agent="github",
        logged_in=False,
        status_text="Not logged in to GitHub",
    )


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
