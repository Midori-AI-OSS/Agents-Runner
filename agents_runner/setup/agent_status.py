"""Agent installation and login status detection.

This module provides functions to detect whether agent CLIs are installed
and whether they are logged in/authenticated.
"""

import json
import os
import shutil
import subprocess

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from agents_runner.agent_cli import normalize_agent


class StatusType(Enum):
    """Agent status types."""

    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    NOT_INSTALLED = "not_installed"
    UNKNOWN = "unknown"


@dataclass
class AgentStatus:
    """Agent installation and authentication status."""

    agent: str
    installed: bool
    logged_in: bool
    status_text: str
    status_type: StatusType
    username: str | None = None
    last_checked: datetime | None = None


def check_agent_installed(agent: str) -> bool:
    """Check if agent CLI is installed (present in PATH).

    Args:
        agent: Agent name (codex, claude, copilot, gemini)

    Returns:
        True if CLI is in PATH, False otherwise
    """
    agent = normalize_agent(agent)
    return shutil.which(agent) is not None


def check_codex_login() -> tuple[bool, str]:
    """Check codex login status.

    Returns:
        (logged_in: bool, status_message: str)
    """
    try:
        result = subprocess.run(
            ["codex", "login", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return (True, "Logged in")
        return (False, "Not logged in")
    except subprocess.TimeoutExpired:
        return (False, "Unknown (timeout)")
    except (FileNotFoundError, OSError):
        return (False, "Unknown (command failed)")


def check_claude_login() -> tuple[bool, str]:
    """Check claude login status.

    Note: Claude Code does not have a simple auth status command.
    We check for the existence of config files as a heuristic.

    Returns:
        (logged_in: bool, status_message: str)
    """
    config_dir = Path.home() / ".claude"
    if not config_dir.exists():
        return (False, "Not logged in (no config)")

    # Check if config directory has files
    try:
        if any(config_dir.iterdir()):
            return (True, "Possibly logged in (config exists)")
    except OSError:
        pass

    return (False, "Not logged in")


def check_copilot_login() -> tuple[bool, str]:
    """Check GitHub Copilot login status via gh CLI.

    Copilot uses GitHub CLI for authentication.

    Returns:
        (logged_in: bool, status_message: str)
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "Logged in" in result.stdout:
            # Try to extract username
            for line in result.stdout.split("\n"):
                if "Logged in to github.com account" in line:
                    parts = line.split("account")
                    if len(parts) > 1:
                        username = parts[1].split("(")[0].strip()
                        return (True, f"Logged in as {username}")
            return (True, "Logged in")
        return (False, "Not logged in to GitHub")
    except subprocess.TimeoutExpired:
        return (False, "Unknown (timeout)")
    except (FileNotFoundError, OSError):
        return (False, "Unknown (gh CLI not found)")


def check_gemini_login() -> tuple[bool, str]:
    """Check Gemini login status.

    Gemini can be authenticated via:
    - GEMINI_API_KEY environment variable
    - ~/.gemini/settings.json configuration file
    - Other Google auth environment variables

    Returns:
        (logged_in: bool, status_message: str)
    """
    # Check environment variables
    if os.environ.get("GEMINI_API_KEY"):
        return (True, "Logged in (GEMINI_API_KEY)")
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        return (True, "Logged in (VERTEXAI)")
    if os.environ.get("GOOGLE_GENAI_USE_GCA"):
        return (True, "Logged in (GCA)")

    # Check settings.json
    settings_path = Path.home() / ".gemini" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                # Look for any auth-related keys
                auth_keys = ["apiKey", "api_key", "vertexai", "gca", "auth"]
                if any(key in settings for key in auth_keys):
                    return (True, "Logged in (settings.json)")
        except (json.JSONDecodeError, OSError):
            pass

    return (False, "Not logged in (no auth method found)")


def check_gh_status() -> tuple[bool, str]:
    """Check GitHub CLI login status.

    This is separate from Copilot as gh CLI is used for PR metadata
    across all agents.

    Returns:
        (logged_in: bool, status_message: str)
    """
    # Same implementation as check_copilot_login but for gh CLI specifically
    return check_copilot_login()


def detect_codex_status() -> AgentStatus:
    """Detect Codex installation and login status.

    Returns:
        AgentStatus with detection results
    """
    installed = check_agent_installed("codex")
    if not installed:
        return AgentStatus(
            agent="codex",
            installed=False,
            logged_in=False,
            status_text="Not installed",
            status_type=StatusType.NOT_INSTALLED,
            last_checked=datetime.now(),
        )

    logged_in, message = check_codex_login()
    return AgentStatus(
        agent="codex",
        installed=True,
        logged_in=logged_in,
        status_text=message,
        status_type=StatusType.LOGGED_IN if logged_in else StatusType.NOT_LOGGED_IN,
        last_checked=datetime.now(),
    )


def detect_claude_status() -> AgentStatus:
    """Detect Claude installation and login status.

    Returns:
        AgentStatus with detection results
    """
    installed = check_agent_installed("claude")
    if not installed:
        return AgentStatus(
            agent="claude",
            installed=False,
            logged_in=False,
            status_text="Not installed",
            status_type=StatusType.NOT_INSTALLED,
            last_checked=datetime.now(),
        )

    logged_in, message = check_claude_login()
    # Claude detection is heuristic, so mark as unknown if config exists
    if logged_in and "Possibly" in message:
        status_type = StatusType.UNKNOWN
    else:
        status_type = StatusType.LOGGED_IN if logged_in else StatusType.NOT_LOGGED_IN

    return AgentStatus(
        agent="claude",
        installed=True,
        logged_in=logged_in,
        status_text=message,
        status_type=status_type,
        last_checked=datetime.now(),
    )


def detect_copilot_status() -> AgentStatus:
    """Detect GitHub Copilot installation and login status.

    Returns:
        AgentStatus with detection results
    """
    installed = check_agent_installed("copilot")
    if not installed:
        return AgentStatus(
            agent="copilot",
            installed=False,
            logged_in=False,
            status_text="Not installed",
            status_type=StatusType.NOT_INSTALLED,
            last_checked=datetime.now(),
        )

    logged_in, message = check_copilot_login()
    # Extract username if present
    username = None
    if "as " in message:
        username = message.split("as ")[-1].strip()

    return AgentStatus(
        agent="copilot",
        installed=True,
        logged_in=logged_in,
        status_text=message,
        status_type=StatusType.LOGGED_IN if logged_in else StatusType.NOT_LOGGED_IN,
        username=username,
        last_checked=datetime.now(),
    )


def detect_gemini_status() -> AgentStatus:
    """Detect Gemini installation and login status.

    Returns:
        AgentStatus with detection results
    """
    installed = check_agent_installed("gemini")
    if not installed:
        return AgentStatus(
            agent="gemini",
            installed=False,
            logged_in=False,
            status_text="Not installed",
            status_type=StatusType.NOT_INSTALLED,
            last_checked=datetime.now(),
        )

    logged_in, message = check_gemini_login()
    return AgentStatus(
        agent="gemini",
        installed=True,
        logged_in=logged_in,
        status_text=message,
        status_type=StatusType.LOGGED_IN if logged_in else StatusType.NOT_LOGGED_IN,
        last_checked=datetime.now(),
    )


def detect_gh_status() -> AgentStatus:
    """Detect GitHub CLI installation and login status.

    Returns:
        AgentStatus with detection results
    """
    installed = check_agent_installed("gh")
    if not installed:
        return AgentStatus(
            agent="github",
            installed=False,
            logged_in=False,
            status_text="Not installed",
            status_type=StatusType.NOT_INSTALLED,
            last_checked=datetime.now(),
        )

    logged_in, message = check_gh_status()
    # Extract username if present
    username = None
    if "as " in message:
        username = message.split("as ")[-1].strip()

    return AgentStatus(
        agent="github",
        installed=True,
        logged_in=logged_in,
        status_text=message,
        status_type=StatusType.LOGGED_IN if logged_in else StatusType.NOT_LOGGED_IN,
        username=username,
        last_checked=datetime.now(),
    )


def detect_all_agents() -> list[AgentStatus]:
    """Detect status for all supported agents and GitHub CLI.

    Returns:
        List of AgentStatus for all agents
    """
    return [
        detect_codex_status(),
        detect_claude_status(),
        detect_copilot_status(),
        detect_gemini_status(),
        detect_gh_status(),
    ]
