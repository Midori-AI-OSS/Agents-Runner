"""
Cooldown manager for tracking agent cooldown state.

Manages cooldown state across agents with persistence support.
"""

from __future__ import annotations

from agents_runner.core.agent.watch_state import AgentWatchState
from agents_runner.core.agent.watch_state import SupportLevel


class CooldownManager:
    """Manages cooldown state for agents."""

    def __init__(self, watch_states: dict[str, AgentWatchState]) -> None:
        """Initialize cooldown manager.

        Args:
            watch_states: Dictionary mapping provider_name -> AgentWatchState
                         This is shared with UI and persistence layer
        """
        self._watch_states = watch_states

    def check_cooldown(self, agent_name: str) -> AgentWatchState | None:
        """Check cooldown state for agent.

        Args:
            agent_name: Agent CLI name (e.g., "codex", "claude")

        Returns:
            AgentWatchState if exists, None otherwise
        """
        return self._watch_states.get(agent_name)

    def is_on_cooldown(self, agent_name: str) -> bool:
        """Check if agent is currently on cooldown.

        Args:
            agent_name: Agent CLI name

        Returns:
            True if agent is on cooldown, False otherwise
        """
        watch_state = self._watch_states.get(agent_name)
        if not watch_state:
            return False
        return watch_state.is_on_cooldown()

    def set_cooldown(
        self, agent_name: str, duration_seconds: int, reason: str = ""
    ) -> AgentWatchState:
        """Set cooldown for agent.

        Args:
            agent_name: Agent CLI name
            duration_seconds: Cooldown duration in seconds
            reason: Reason for cooldown (error message)

        Returns:
            Updated AgentWatchState
        """
        from agents_runner.core.agent.rate_limit import RateLimitDetector

        # Get or create watch state
        watch_state = self._watch_states.get(agent_name)
        if not watch_state:
            watch_state = AgentWatchState(
                provider_name=agent_name,
                support_level=SupportLevel.BEST_EFFORT,
            )
            self._watch_states[agent_name] = watch_state

        # Record rate-limit event
        RateLimitDetector.record_rate_limit(
            watch_state, duration_seconds, reason
        )

        return watch_state

    def clear_cooldown(self, agent_name: str) -> None:
        """Clear cooldown for agent (user bypass).

        Args:
            agent_name: Agent CLI name
        """
        from agents_runner.core.agent.rate_limit import RateLimitDetector

        watch_state = self._watch_states.get(agent_name)
        if watch_state:
            RateLimitDetector.clear_cooldown(watch_state)

    def get_all_states(self) -> dict[str, AgentWatchState]:
        """Get all watch states.

        Returns:
            Dictionary of all watch states
        """
        return self._watch_states
