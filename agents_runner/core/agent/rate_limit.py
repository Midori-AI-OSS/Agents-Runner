"""
Rate limit detection and cooldown management.

Detects rate-limit errors from agent logs and manages cooldown state.
"""

from __future__ import annotations

import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from agents_runner.core.agent.watch_state import AgentStatus
from agents_runner.core.agent.watch_state import AgentWatchState


class RateLimitDetector:
    """Detects rate-limit errors from agent logs and exit codes."""

    # Per-agent rate-limit patterns with default cooldown durations (seconds)
    # Pattern with None duration means extract from message
    PATTERNS = {
        "codex": [
            (r"rate.?limit.*exceeded", 3600),
            (r"429.*too.?many.?requests", 60),
            (r"quota.*exceeded", 3600),  # Longer cooldown for quota
            (r"retry.*after.*(\d+)", None),  # Extract duration
        ],
        "claude": [
            (r"rate_limit_error", 60),
            (r"too.?many.?requests", 60),
            (r"429", 60),
        ],
        "copilot": [
            (r"rate limit.*exceeded", 60),
            (r"wait.*(\d+).*seconds?", None),  # Extract duration
        ],
        "gemini": [
            (r"quota exceeded", 60),
            (r"rate limit", 60),
            (r"429", 60),
            (r"resource_exhausted", 60),
        ],
    }

    @staticmethod
    def detect(
        agent_cli: str,
        exit_code: int,
        logs: list[str],
        container_state: dict[str, Any] | None = None,
    ) -> tuple[bool, int]:
        """Detect rate-limit error and extract cooldown duration.

        Args:
            agent_cli: Agent CLI name ("codex", "claude", etc.)
            exit_code: Container exit code
            logs: Container log lines
            container_state: Optional container state dict

        Returns:
            (is_rate_limited, cooldown_seconds)
            If not rate-limited, returns (False, 0)
            If rate-limited, returns (True, duration_in_seconds)
        """
        # Check exit code (429 = Too Many Requests in HTTP)
        if exit_code == 429:
            return True, 3600  # Default 1 hour for HTTP 429

        # Get patterns for this agent
        patterns = RateLimitDetector.PATTERNS.get(agent_cli, [])

        # Scan recent logs (last 100 lines)
        for line in logs[-100:]:
            line_lower = line.lower()

            for pattern, default_cooldown in patterns:
                match = re.search(pattern, line_lower)
                if not match:
                    continue

                # Found rate-limit indicator
                if default_cooldown is None:
                    # Pattern includes duration extraction
                    try:
                        duration = int(match.group(1))
                        return True, duration
                    except (IndexError, ValueError):
                        return True, 3600  # Fallback to 1 hour
                else:
                    return True, default_cooldown

        return False, 0

    @staticmethod
    def record_rate_limit(
        watch_state: AgentWatchState,
        cooldown_seconds: int,
        reason: str = "",
    ) -> None:
        """Record rate-limit event in watch state.

        Args:
            watch_state: Agent watch state to update
            cooldown_seconds: Cooldown duration in seconds
            reason: Human-readable reason (log excerpt)
        """
        now = datetime.now(timezone.utc)
        watch_state.last_rate_limited_at = now
        watch_state.cooldown_until = now + timedelta(seconds=cooldown_seconds)
        watch_state.cooldown_reason = reason
        watch_state.status = AgentStatus.ON_COOLDOWN

    @staticmethod
    def clear_cooldown(watch_state: AgentWatchState) -> None:
        """Clear cooldown state (user bypass)."""
        watch_state.cooldown_until = None
        watch_state.status = AgentStatus.READY
