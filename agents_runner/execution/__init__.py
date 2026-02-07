"""
Task execution supervision module.

Provides retry, fallback, and error classification for agent task execution.
"""

from agents_runner.execution.supervisor import TaskSupervisor
from agents_runner.execution.supervisor_errors import calculate_backoff
from agents_runner.execution.supervisor_errors import classify_error
from agents_runner.execution.supervisor_types import ErrorType
from agents_runner.execution.supervisor_types import SupervisorConfig
from agents_runner.execution.supervisor_types import SupervisorResult

__all__ = [
    "ErrorType",
    "SupervisorConfig",
    "SupervisorResult",
    "TaskSupervisor",
    "calculate_backoff",
    "classify_error",
]
