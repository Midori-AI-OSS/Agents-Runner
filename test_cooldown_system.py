"""
Test cooldown system functionality.

This test validates the rate-limit detection and cooldown management.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from agents_runner.core.agent.cooldown_manager import CooldownManager
from agents_runner.core.agent.rate_limit import RateLimitDetector
from agents_runner.core.agent.watch_state import (
    AgentStatus,
    AgentWatchState,
    SupportLevel,
)


def test_rate_limit_detection():
    """Test rate-limit detection from logs."""
    # Test Codex rate limit
    logs = [
        "Starting task...",
        "Error: rate limit exceeded for model gpt-4",
        "Please retry after 60 seconds",
    ]
    is_rate_limited, cooldown = RateLimitDetector.detect(
        "codex", 0, logs, None
    )
    assert is_rate_limited is True
    assert cooldown == 3600  # Default 1 hour for rate limit exceeded

    # Test 429 status code
    logs = ["HTTP 429 Too Many Requests"]
    is_rate_limited, cooldown = RateLimitDetector.detect(
        "codex", 0, logs, None
    )
    assert is_rate_limited is True
    assert cooldown == 60  # Default for 429

    # Test no rate limit
    logs = ["Task completed successfully"]
    is_rate_limited, cooldown = RateLimitDetector.detect(
        "codex", 0, logs, None
    )
    assert is_rate_limited is False
    assert cooldown == 0

    print("✓ Rate-limit detection tests passed")


def test_cooldown_manager():
    """Test cooldown manager functionality."""
    watch_states: dict[str, AgentWatchState] = {}
    cooldown_mgr = CooldownManager(watch_states)

    # Test setting cooldown
    watch_state = cooldown_mgr.set_cooldown(
        "codex", 3600, "Rate limit exceeded"
    )
    assert watch_state.provider_name == "codex"
    assert watch_state.status == AgentStatus.ON_COOLDOWN
    assert watch_state.cooldown_reason == "Rate limit exceeded"
    assert watch_state.is_on_cooldown() is True

    # Test checking cooldown
    assert cooldown_mgr.is_on_cooldown("codex") is True
    assert cooldown_mgr.is_on_cooldown("claude") is False

    # Test clearing cooldown
    cooldown_mgr.clear_cooldown("codex")
    assert cooldown_mgr.is_on_cooldown("codex") is False
    assert watch_state.status == AgentStatus.READY

    print("✓ Cooldown manager tests passed")


def test_watch_state():
    """Test watch state functionality."""
    # Create watch state with cooldown
    now = datetime.now(timezone.utc)
    future = now + timedelta(seconds=3600)

    watch_state = AgentWatchState(
        provider_name="codex",
        support_level=SupportLevel.BEST_EFFORT,
        status=AgentStatus.ON_COOLDOWN,
        cooldown_until=future,
        cooldown_reason="Test cooldown",
    )

    # Test is_on_cooldown
    assert watch_state.is_on_cooldown() is True

    # Test cooldown_seconds_remaining
    remaining = watch_state.cooldown_seconds_remaining()
    assert 3595 <= remaining <= 3605  # Allow for processing time

    # Test expired cooldown
    past = now - timedelta(seconds=60)
    watch_state.cooldown_until = past
    assert watch_state.is_on_cooldown() is False
    assert watch_state.cooldown_seconds_remaining() == 0.0

    print("✓ Watch state tests passed")


def test_record_rate_limit():
    """Test recording rate-limit event."""
    watch_state = AgentWatchState(
        provider_name="codex",
        support_level=SupportLevel.BEST_EFFORT,
    )

    # Record rate-limit event
    RateLimitDetector.record_rate_limit(
        watch_state, 3600, "Rate limit exceeded"
    )

    assert watch_state.status == AgentStatus.ON_COOLDOWN
    assert watch_state.cooldown_reason == "Rate limit exceeded"
    assert watch_state.last_rate_limited_at is not None
    assert watch_state.cooldown_until is not None
    assert watch_state.is_on_cooldown() is True

    # Clear cooldown
    RateLimitDetector.clear_cooldown(watch_state)
    assert watch_state.status == AgentStatus.READY
    assert watch_state.cooldown_until is None

    print("✓ Record rate-limit tests passed")


def main():
    """Run all tests."""
    print("Running cooldown system tests...\n")

    test_rate_limit_detection()
    test_cooldown_manager()
    test_watch_state()
    test_record_rate_limit()

    print("\n✓ All tests passed!")


if __name__ == "__main__":
    main()
