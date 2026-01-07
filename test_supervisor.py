"""
Unit tests for supervisor error classification and backoff calculation.

Run with: python -m pytest test_supervisor.py
"""

from agents_runner.execution.supervisor import ErrorType
from agents_runner.execution.supervisor import calculate_backoff
from agents_runner.execution.supervisor import classify_error


def test_classify_error_container_crash_oom():
    """Test OOMKilled detection."""
    result = classify_error(
        exit_code=137,
        container_state={"OOMKilled": True},
        logs=["Task running", "Memory exceeded"],
    )
    assert result == ErrorType.CONTAINER_CRASH


def test_classify_error_container_crash_sigkill():
    """Test SIGKILL (exit 137) detection."""
    result = classify_error(
        exit_code=137,
        container_state={},
        logs=["Task running"],
    )
    assert result == ErrorType.CONTAINER_CRASH


def test_classify_error_rate_limit():
    """Test rate limit detection from logs."""
    logs = [
        "Starting task",
        "Calling API",
        "Error: 429 Too Many Requests",
        "Rate limit exceeded",
    ]
    result = classify_error(
        exit_code=1,
        container_state={},
        logs=logs,
    )
    assert result == ErrorType.RATE_LIMIT


def test_classify_error_fatal_auth():
    """Test fatal authentication error."""
    logs = [
        "Starting task",
        "Calling API",
        "Error: Authentication failed",
        "Invalid API key",
    ]
    result = classify_error(
        exit_code=1,
        container_state={},
        logs=logs,
    )
    assert result == ErrorType.FATAL


def test_classify_error_agent_failure_command_not_found():
    """Test agent command not found."""
    logs = [
        "Starting task",
        "bash: codex: command not found",
    ]
    result = classify_error(
        exit_code=127,
        container_state={},
        logs=logs,
    )
    assert result == ErrorType.AGENT_FAILURE


def test_classify_error_agent_failure_exit_127():
    """Test exit code 127 (command not found)."""
    result = classify_error(
        exit_code=127,
        container_state={},
        logs=["Task running"],
    )
    assert result == ErrorType.AGENT_FAILURE


def test_classify_error_retryable_generic():
    """Test generic retryable error."""
    logs = [
        "Starting task",
        "Network error",
        "Connection reset by peer",
    ]
    result = classify_error(
        exit_code=1,
        container_state={},
        logs=logs,
    )
    assert result == ErrorType.RETRYABLE


def test_classify_error_retryable_exit_1():
    """Test exit 1 without specific patterns defaults to retryable."""
    result = classify_error(
        exit_code=1,
        container_state={},
        logs=["Task failed"],
    )
    assert result == ErrorType.RETRYABLE


def test_calculate_backoff_standard():
    """Test standard backoff progression."""
    assert calculate_backoff(0, ErrorType.RETRYABLE) == 5.0
    assert calculate_backoff(1, ErrorType.RETRYABLE) == 15.0
    assert calculate_backoff(2, ErrorType.RETRYABLE) == 45.0
    assert calculate_backoff(3, ErrorType.RETRYABLE) == 45.0  # Max


def test_calculate_backoff_rate_limit():
    """Test rate limit backoff progression."""
    assert calculate_backoff(0, ErrorType.RATE_LIMIT) == 60.0
    assert calculate_backoff(1, ErrorType.RATE_LIMIT) == 120.0
    assert calculate_backoff(2, ErrorType.RATE_LIMIT) == 300.0
    assert calculate_backoff(3, ErrorType.RATE_LIMIT) == 300.0  # Max


def test_calculate_backoff_container_crash():
    """Test container crash uses standard backoff."""
    assert calculate_backoff(0, ErrorType.CONTAINER_CRASH) == 5.0
    assert calculate_backoff(1, ErrorType.CONTAINER_CRASH) == 15.0


def test_classify_error_priority_oom_over_logs():
    """Test OOMKilled takes priority over log patterns."""
    logs = [
        "Starting task",
        "Rate limit exceeded",  # Would normally trigger RATE_LIMIT
    ]
    result = classify_error(
        exit_code=1,
        container_state={"OOMKilled": True},
        logs=logs,
    )
    assert result == ErrorType.CONTAINER_CRASH


def test_classify_error_priority_fatal_over_retryable():
    """Test fatal patterns take priority over generic errors."""
    logs = [
        "Starting task",
        "Connection error",  # Generic
        "Authentication failed",  # Fatal
        "Invalid API key",
    ]
    result = classify_error(
        exit_code=1,
        container_state={},
        logs=logs,
    )
    assert result == ErrorType.FATAL


def test_classify_error_case_insensitive():
    """Test pattern matching is case insensitive."""
    logs = [
        "RATE LIMIT EXCEEDED",
        "Too Many Requests",
    ]
    result = classify_error(
        exit_code=1,
        container_state={},
        logs=logs,
    )
    assert result == ErrorType.RATE_LIMIT


if __name__ == "__main__":
    # Simple test runner
    import sys

    tests = [
        test_classify_error_container_crash_oom,
        test_classify_error_container_crash_sigkill,
        test_classify_error_rate_limit,
        test_classify_error_fatal_auth,
        test_classify_error_agent_failure_command_not_found,
        test_classify_error_agent_failure_exit_127,
        test_classify_error_retryable_generic,
        test_classify_error_retryable_exit_1,
        test_calculate_backoff_standard,
        test_calculate_backoff_rate_limit,
        test_calculate_backoff_container_crash,
        test_classify_error_priority_oom_over_logs,
        test_classify_error_priority_fatal_over_retryable,
        test_classify_error_case_insensitive,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: ERROR {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
