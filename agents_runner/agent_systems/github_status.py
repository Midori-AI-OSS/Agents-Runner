"""GitHub authentication status presentation shared by setup integrations."""

from agents_runner.agent_systems.status import AgentStatus
from agents_runner.agent_systems.status import installed_status
from agents_runner.agent_systems.status import unknown_installed_status
from agents_runner.gh.auth import GhAuthError
from agents_runner.gh.auth import GhAuthSnapshot


def github_auth_status(*, agent: str, snapshot: GhAuthSnapshot) -> AgentStatus:
    """Convert a shared GitHub authentication snapshot to UI status."""

    if snapshot.error == GhAuthError.TIMEOUT:
        return unknown_installed_status(agent=agent, message="Unknown (timeout)")
    if snapshot.error == GhAuthError.UNAVAILABLE:
        return unknown_installed_status(agent=agent, message="Unknown (gh CLI not found)")
    if snapshot.authenticated and snapshot.login:
        return installed_status(
            agent=agent, logged_in=True, status_text=f"Logged in as {snapshot.login}", username=snapshot.login
        )
    if snapshot.authenticated:
        return installed_status(agent=agent, logged_in=True, status_text="Logged in")
    return installed_status(agent=agent, logged_in=False, status_text="Not logged in to GitHub")
