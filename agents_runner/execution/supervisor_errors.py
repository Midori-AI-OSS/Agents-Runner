"""
Error classification and failure analysis for task supervisor.

Provides utilities to classify execution errors, calculate backoff delays,
and analyze failure reasons from container state and logs.
"""

from __future__ import annotations

import re
from typing import Any

from agents_runner.execution.supervisor_types import ErrorType
from agents_runner.execution.supervisor_types import FailureReason


def classify_error(
    exit_code: int,
    container_state: dict[str, Any],
    logs: list[str],
) -> ErrorType:
    """Classify execution error to determine retry/fallback strategy.

    Args:
        exit_code: Container exit code
        container_state: Docker container state inspection
        logs: Container log lines

    Returns:
        ErrorType indicating how to handle this failure
    """
    # Container crash (highest priority)
    if container_state.get("OOMKilled", False):
        return ErrorType.CONTAINER_CRASH

    # Check for SIGKILL (exit 137)
    if exit_code == 137:
        return ErrorType.CONTAINER_CRASH

    # Rate limit detection (scan recent logs)
    rate_limit_patterns = [
        r"rate.?limit",
        r"429",
        r"too.?many.?requests",
        r"quota.?exceeded",
        r"retry.?after",
    ]
    for line in logs[-100:]:
        line_lower = line.lower()
        for pattern in rate_limit_patterns:
            if re.search(pattern, line_lower):
                return ErrorType.RATE_LIMIT

    # Fatal error patterns (authentication, permissions)
    fatal_patterns = [
        r"authentication.?failed",
        r"invalid.?api.?key",
        r"permission.?denied",
        r"unauthorized",
        r"forbidden",
        r"access.?denied",
        r"invalid.?credentials",
    ]
    for line in logs[-50:]:
        line_lower = line.lower()
        for pattern in fatal_patterns:
            if re.search(pattern, line_lower):
                return ErrorType.FATAL

    # Agent-specific failure patterns
    agent_failure_patterns = [
        r"command.?not.?found",
        r"no such file.*codex",
        r"no such file.*claude",
        r"no such file.*copilot",
        r"no such file.*gemini",
        r"bash:.*not found",
        r"agent.?not.?available",
        r"agent.?not.?installed",
    ]
    for line in logs[-50:]:
        line_lower = line.lower()
        for pattern in agent_failure_patterns:
            if re.search(pattern, line_lower):
                return ErrorType.AGENT_FAILURE

    # Exit code analysis
    if exit_code in {126, 127}:  # Command not executable / not found
        return ErrorType.AGENT_FAILURE

    # Default to retryable for non-zero exit codes
    if exit_code != 0:
        return ErrorType.RETRYABLE

    # Should not reach here (success case)
    return ErrorType.RETRYABLE


def calculate_backoff(
    retry_count: int, error_type: ErrorType
) -> float:  # pragma: no cover
    """Calculate backoff delay in seconds for retry attempt.

    Args:
        retry_count: Number of retries already attempted (0-indexed)
        error_type: Type of error that occurred

    Returns:
        Delay in seconds before retry
    """
    if error_type == ErrorType.RATE_LIMIT:
        # Longer backoff for rate limits: 1m, 2m, 5m
        delays = [60.0, 120.0, 300.0]
    else:
        # Standard backoff: 5s, 15s, 45s
        delays = [5.0, 15.0, 45.0]

    return delays[min(retry_count, len(delays) - 1)]


def classify_failure_reason(
    *,
    exit_code: int,
    container_state: dict[str, Any],
    logs: list[str],
    exit_summary: str | None,
) -> FailureReason:
    """Classify failure reason from execution context.

    Args:
        exit_code: Container exit code
        container_state: Docker container state inspection
        logs: Container log lines
        exit_summary: Optional error summary from execution

    Returns:
        FailureReason with category, message, and matched signals
    """
    combined = "\n".join([*(logs or []), str(exit_summary or "")])
    combined_lower = combined.lower()

    # Rate limit/quota signals (minimum required set)
    rate_signals = [
        ("429", "contains: 429"),
        ("rate limit", "contains: rate limit"),
        ("quota", "contains: quota"),
        (
            "exceeded your copilot token usage",
            "contains: exceeded your Copilot token usage",
        ),
        ("capierror: 429", "contains: CAPIError: 429"),
    ]
    matched_rate: list[str] = []
    for token, label in rate_signals:
        if token in combined_lower:
            matched_rate.append(label)
    if matched_rate:
        return FailureReason(
            failure_category="rate_limit",
            failure_message="rate limit or quota exhaustion detected",
            matched_signals=tuple(matched_rate),
        )

    # Container crash
    if container_state.get("OOMKilled", False) or exit_code == 137:
        return FailureReason(
            failure_category="tool_error",
            failure_message="container crashed (OOMKilled or SIGKILL)",
            matched_signals=("container_crash",),
        )

    # Auth signals
    auth_patterns = [
        (r"authentication.?failed", "authentication failed"),
        (r"invalid.?api.?key", "invalid api key"),
        (r"unauthorized", "unauthorized"),
        (r"forbidden", "forbidden"),
        (r"invalid.?credentials", "invalid credentials"),
    ]
    auth_hits: list[str] = []
    for pattern, label in auth_patterns:
        if re.search(pattern, combined_lower):
            auth_hits.append(label)
    if auth_hits:
        return FailureReason(
            failure_category="auth",
            failure_message="authentication/authorization failure detected",
            matched_signals=tuple(auth_hits),
        )

    # Tooling signals
    tool_patterns = [
        (r"command.?not.?found", "command not found"),
        (r"no such file", "no such file"),
        (r"not installed", "not installed"),
    ]
    tool_hits: list[str] = []
    for pattern, label in tool_patterns:
        if re.search(pattern, combined_lower):
            tool_hits.append(label)
    if exit_code in {126, 127}:
        tool_hits.append(f"exit_code={exit_code}")
    if tool_hits:
        return FailureReason(
            failure_category="tool_error",
            failure_message="agent/tool execution failure detected",
            matched_signals=tuple(tool_hits),
        )

    # Network signals
    network_patterns = [
        (r"timed? out", "timeout"),
        (r"connection (refused|reset)", "connection reset/refused"),
        (r"temporary failure", "temporary failure"),
        (r"network is unreachable", "network unreachable"),
        (r"dns", "dns"),
        (r"tls|ssl", "tls/ssl"),
    ]
    network_hits: list[str] = []
    for pattern, label in network_patterns:
        if re.search(pattern, combined_lower):
            network_hits.append(label)
    if network_hits:
        return FailureReason(
            failure_category="network",
            failure_message="network failure detected",
            matched_signals=tuple(network_hits),
        )

    return FailureReason(
        failure_category="unknown",
        failure_message="unknown failure",
        matched_signals=(),
    )
