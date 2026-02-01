"""
Type definitions and data classes for task supervisor.

Contains configuration, result types, and supporting data structures
used throughout the supervision system.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from typing import Literal


class ErrorType(Enum):
    """Classification of task execution errors."""

    RETRYABLE = "retryable"  # Transient network/system errors
    RATE_LIMIT = "rate_limit"  # API rate limit (needs longer backoff)
    AGENT_FAILURE = "agent_failure"  # Agent-specific failure (try fallback)
    FATAL = "fatal"  # Unrecoverable (bad auth, invalid prompt)
    CONTAINER_CRASH = "container_crash"  # OOMKilled, segfault


@dataclass
class SupervisorConfig:
    """Configuration for task supervision."""

    max_retries_per_agent: int = 0
    enable_fallback: bool = True
    backoff_base_seconds: float = 5.0
    rate_limit_backoff_base: float = 60.0


@dataclass
class SupervisorResult:
    """Result of supervised task execution."""

    exit_code: int
    error: str | None
    artifacts: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


FailureCategory = Literal["rate_limit", "auth", "network", "tool_error", "unknown"]


@dataclass(frozen=True, slots=True)
class FailureReason:
    failure_category: FailureCategory
    failure_message: str
    matched_signals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AttemptKey:
    agent_cli: str
    host_config_dir: str
    agent_cli_args: tuple[str, ...]
