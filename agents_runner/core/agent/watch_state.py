"""
Agent watch state data models.

Tracks usage, quota, and cooldown state for agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any


class SupportLevel(Enum):
    """Level of usage watching support for an agent."""

    FULL = "full"  # API available, watcher implemented
    BEST_EFFORT = "best_effort"  # No API, detect from errors only
    UNKNOWN = "unknown"  # Not yet investigated


class AgentStatus(Enum):
    """Current operational status of an agent."""

    READY = "ready"  # Available for use
    ON_COOLDOWN = "on_cooldown"  # Rate-limited, cooling down
    QUOTA_LOW = "quota_low"  # <10% quota remaining
    QUOTA_EXHAUSTED = "quota_exhausted"  # 0% quota remaining
    UNAVAILABLE = "unavailable"  # Not installed/configured


@dataclass
class UsageWindow:
    """A single usage/quota window (e.g., hourly, daily, weekly)."""

    name: str  # "5h", "weekly", "daily", etc.
    used: int  # Requests used
    limit: int  # Request limit
    remaining: int  # Requests remaining
    remaining_percent: float  # Percentage remaining (0-100)
    reset_at: datetime | None  # When window resets


@dataclass
class AgentWatchState:
    """Complete watch state for a single agent."""

    # Identity
    provider_name: str  # "codex", "claude", "copilot", "gemini"

    # Support level
    support_level: SupportLevel = SupportLevel.UNKNOWN

    # Current status
    status: AgentStatus = AgentStatus.READY

    # Usage windows (optional, only if watcher available)
    windows: list[UsageWindow] = field(default_factory=list)

    # Cooldown tracking (reactive)
    last_rate_limited_at: datetime | None = None
    cooldown_until: datetime | None = None
    cooldown_reason: str = ""  # Error message that triggered cooldown

    # Last check metadata
    last_checked_at: datetime | None = None
    last_error: str = ""  # Last watcher error, if any

    # Raw response (for debugging)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def is_on_cooldown(self) -> bool:
        """Check if agent is currently on cooldown."""
        if not self.cooldown_until:
            return False
        return datetime.now(timezone.utc) < self.cooldown_until

    def cooldown_seconds_remaining(self) -> float:
        """Get seconds remaining in cooldown, or 0 if not on cooldown."""
        if not self.is_on_cooldown():
            return 0.0
        if not self.cooldown_until:
            return 0.0
        delta = self.cooldown_until - datetime.now(timezone.utc)
        return max(0.0, delta.total_seconds())

    def primary_window_display(self) -> str:
        """Get display string for primary usage window."""
        if not self.windows:
            return "Unknown"
        primary = self.windows[0]
        return f"{primary.name}: {primary.remaining_percent:.0f}% left"

    def all_windows_display(self) -> str:
        """Get display string for all usage windows."""
        if not self.windows:
            return "Unknown"
        parts = [
            f"{w.name}: {w.remaining_percent:.0f}% left" for w in self.windows
        ]
        return " • ".join(parts)
