from __future__ import annotations

import shutil

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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


def command_in_path(command: str) -> bool:
    """Check whether a command exists in PATH."""

    raw = str(command or "").strip().lower()
    if not raw:
        return False
    return shutil.which(raw) is not None


def status_now() -> datetime:
    return datetime.now()


def not_installed_status(*, agent: str) -> AgentStatus:
    return AgentStatus(
        agent=agent,
        installed=False,
        logged_in=False,
        status_text="Not installed",
        status_type=StatusType.NOT_INSTALLED,
        last_checked=status_now(),
    )


def installed_status(
    *,
    agent: str,
    logged_in: bool,
    status_text: str,
    status_type: StatusType | None = None,
    username: str | None = None,
) -> AgentStatus:
    resolved_status_type = status_type
    if resolved_status_type is None:
        resolved_status_type = StatusType.LOGGED_IN if logged_in else StatusType.NOT_LOGGED_IN
    return AgentStatus(
        agent=agent,
        installed=True,
        logged_in=logged_in,
        status_text=status_text,
        status_type=resolved_status_type,
        username=username,
        last_checked=status_now(),
    )


def unknown_installed_status(*, agent: str, message: str) -> AgentStatus:
    return installed_status(
        agent=agent,
        logged_in=False,
        status_text=message,
        status_type=StatusType.UNKNOWN,
    )
