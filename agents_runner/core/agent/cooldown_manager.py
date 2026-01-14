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

    def check_cooldown(self, agent_key: str) -> AgentWatchState | None:
        """Check cooldown state for an agent selection key.

        Args:
            agent_key: Agent selection key (e.g., "copilot::<dir>::<args>")

        Returns:
            AgentWatchState if exists, None otherwise
        """
        agent_key = str(agent_key or "").strip()
        if not agent_key:
            return None
        watch_state = self._watch_states.get(agent_key)
        if watch_state is not None:
            return watch_state

        # Backwards compatibility: callers may pass the bare agent CLI (e.g. "copilot").
        agent_cli = agent_key.lower()
        if "::" not in agent_cli:
            watch_state = self._watch_states.get(agent_cli)
            if watch_state is not None:
                return watch_state
            for key, candidate in self._watch_states.items():
                if key.startswith(f"{agent_cli}::") and candidate.is_on_cooldown():
                    return candidate
        return None

    def is_on_cooldown(self, agent_key: str) -> bool:
        """Check if an agent selection key is currently on cooldown.

        Args:
            agent_key: Agent selection key or bare agent CLI name

        Returns:
            True if agent is on cooldown, False otherwise
        """
        watch_state = self.check_cooldown(agent_key)
        return bool(watch_state and watch_state.is_on_cooldown())

    def set_cooldown(
        self, agent_key: str, duration_seconds: int, reason: str = ""
    ) -> AgentWatchState:
        """Set cooldown for an agent selection key.

        Args:
            agent_key: Agent selection key or bare agent CLI name
            duration_seconds: Cooldown duration in seconds
            reason: Reason for cooldown (error message)

        Returns:
            Updated AgentWatchState
        """
        from agents_runner.core.agent.rate_limit import RateLimitDetector

        # Get or create watch state
        agent_key = str(agent_key or "").strip()
        watch_state = self._watch_states.get(agent_key)
        if not watch_state:
            watch_state = AgentWatchState(
                provider_name=agent_key,
                support_level=SupportLevel.BEST_EFFORT,
            )
            self._watch_states[agent_key] = watch_state

        # Record rate-limit event
        RateLimitDetector.record_rate_limit(
            watch_state, duration_seconds, reason
        )

        return watch_state

    def clear_cooldown(self, agent_key: str) -> None:
        """Clear cooldown for an agent selection key (user bypass).

        Args:
            agent_key: Agent selection key or bare agent CLI name
        """
        from agents_runner.core.agent.rate_limit import RateLimitDetector

        agent_key = str(agent_key or "").strip()
        watch_state = self._watch_states.get(agent_key)
        if watch_state:
            RateLimitDetector.clear_cooldown(watch_state)

    def get_all_states(self) -> dict[str, AgentWatchState]:
        """Get all watch states.

        Returns:
            Dictionary of all watch states
        """
        return self._watch_states
