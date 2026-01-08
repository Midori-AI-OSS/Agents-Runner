"""
Task supervisor with retry, fallback, and error classification.

Supervises agent task execution with automatic retry on failure,
fallback to alternate agents, and intelligent error classification.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from typing import Callable
from typing import Literal

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker_runner import DockerAgentWorker
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection


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

    max_retries_per_agent: int = 3
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


def calculate_backoff(retry_count: int, error_type: ErrorType) -> float:
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


class TaskSupervisor:
    """Supervises task execution with retry and fallback capabilities.

    Manages agent task execution with:
    - Automatic retry on transient failures (up to 3 times per agent)
    - Exponential backoff between retries
    - Fallback to alternate agents after retry exhaustion
    - Container restart on crash
    - Clean state between retries
    """

    def __init__(
        self,
        config: DockerRunnerConfig,
        prompt: str,
        agent_selection: AgentSelection | None,
        supervisor_config: SupervisorConfig,
        on_state: Callable[[dict[str, Any]], None],
        on_log: Callable[[str], None],
        on_retry: Callable[[int, str, float], None],
        on_agent_switch: Callable[[str, str], None],
        on_done: Callable[[int, str | None, list[str], dict[str, Any]], None] | None = None,
        watch_states: dict[str, Any] | None = None,
    ) -> None:
        """Initialize task supervisor.

        Args:
            config: Docker runner configuration
            prompt: Task prompt
            agent_selection: Agent selection configuration (may be None)
            supervisor_config: Supervisor behavior configuration
            on_state: Callback for state updates
            on_log: Callback for log messages
            on_retry: Callback for retry attempts (retry_count, agent, delay)
            on_agent_switch: Callback for agent switches (from_agent, to_agent)
            on_done: Callback for completion (exit_code, error, artifacts, metadata)
            watch_states: Dict of agent watch states for cooldown tracking
        """
        self._config = config
        self._prompt = prompt
        self._agent_selection = agent_selection
        self._supervisor_config = supervisor_config
        self._on_state = on_state
        self._on_log = on_log
        self._on_retry = on_retry
        self._on_agent_switch = on_agent_switch
        self._on_done = on_done
        self._watch_states = watch_states or {}

        # State tracking
        self._agent_chain: list[AgentInstance] = []
        self._current_agent_index = 0
        self._retry_counts: dict[str, int] = {}
        self._total_attempts = 0
        self._current_worker: DockerAgentWorker | None = None

        # Worker results
        self._last_exit_code = 0
        self._last_error: str | None = None
        self._last_artifacts: list[str] = []
        self._last_logs: list[str] = []
        self._last_container_state: dict[str, Any] = {}
        self._user_stop_reason: Literal["cancel", "kill"] | None = None

    @property
    def container_id(self) -> str | None:
        """Get current worker's container ID."""
        if self._current_worker:
            return self._current_worker.container_id
        return None

    @property
    def gh_repo_root(self) -> str | None:
        """Get current worker's GitHub repo root."""
        if self._current_worker:
            return self._current_worker.gh_repo_root
        return None

    @property
    def gh_base_branch(self) -> str | None:
        """Get current worker's GitHub base branch."""
        if self._current_worker:
            return self._current_worker.gh_base_branch
        return None

    @property
    def gh_branch(self) -> str | None:
        """Get current worker's GitHub branch."""
        if self._current_worker:
            return self._current_worker.gh_branch
        return None

    def request_stop(self) -> None:
        """Request stop of current worker."""
        if self._current_worker:
            self._current_worker.request_stop()

    def request_user_cancel(self) -> None:
        """User requested graceful cancellation (terminal, no retry/fallback)."""
        if self._user_stop_reason is None:
            self._user_stop_reason = "cancel"
            self._on_log("[supervisor] user_cancel requested")
        if self._current_worker:
            self._current_worker.request_stop()

    def request_user_kill(self) -> None:
        """User requested force kill (terminal, no retry/fallback)."""
        if self._user_stop_reason is None:
            self._user_stop_reason = "kill"
            self._on_log("[supervisor] user_kill requested")
        if self._current_worker:
            request_kill = getattr(self._current_worker, "request_kill", None)
            if callable(request_kill):
                request_kill()
            else:
                self._current_worker.request_stop()

    def run(self) -> SupervisorResult:
        """Execute task with supervision.

        Returns:
            SupervisorResult with exit code, error, artifacts, and metadata
        """
        self._initialize_agent_chain()

        # Main supervision loop
        while self._current_agent_index < len(self._agent_chain):
            if self._user_stop_reason is not None:
                result = self._result_for_user_stop()
                self._on_log("[supervisor] retry skipped due to user stop")
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        result.error,
                        result.artifacts,
                        result.metadata,
                    )
                return result

            agent = self._agent_chain[self._current_agent_index]

            # Try executing with current agent
            result = self._try_agent(agent)

            if self._user_stop_reason is not None:
                self._on_log("[supervisor] retry skipped due to user stop")
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        None,
                        result.artifacts,
                        dict(result.metadata, user_stop=self._user_stop_reason),
                    )
                return SupervisorResult(
                    exit_code=result.exit_code,
                    error=None,
                    artifacts=result.artifacts,
                    metadata=dict(result.metadata, user_stop=self._user_stop_reason),
                )

            # Success
            if result.exit_code == 0:
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        result.error,
                        result.artifacts,
                        result.metadata,
                    )
                return result

            # Classify error
            error_type = classify_error(
                result.exit_code,
                self._last_container_state,
                self._last_logs,
            )

            # Record cooldown if rate-limited
            if error_type == ErrorType.RATE_LIMIT:
                self._record_cooldown(agent)

            # Fatal errors don't retry
            if error_type == ErrorType.FATAL:
                self._on_log(f"[supervisor] fatal error detected, no retry")
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        result.error,
                        result.artifacts,
                        result.metadata,
                    )
                return result

            # Check retry count for current agent
            retry_count = self._retry_counts.get(agent.agent_id, 0)

            # Retry if under limit
            if retry_count < self._supervisor_config.max_retries_per_agent:
                self._retry_counts[agent.agent_id] = retry_count + 1
                delay = calculate_backoff(retry_count, error_type)
                self._on_retry(retry_count + 1, agent.agent_cli, delay)
                self._on_log(
                    f"[supervisor] retry {retry_count + 1}/{self._supervisor_config.max_retries_per_agent} "
                    f"with {agent.agent_cli} in {delay:.0f}s"
                )
                if not self._sleep_with_cancel(delay):
                    result = self._result_for_user_stop()
                    self._on_log("[supervisor] retry skipped due to user stop")
                    if self._on_done:
                        self._on_done(
                            result.exit_code,
                            result.error,
                            result.artifacts,
                            result.metadata,
                        )
                    return result
                continue

            # Retries exhausted, try fallback
            if self._current_agent_index + 1 < len(self._agent_chain):
                old_agent = agent.agent_cli
                self._current_agent_index += 1
                new_agent = self._agent_chain[self._current_agent_index]
                self._on_log(
                    f"[supervisor] switching from {old_agent} to {new_agent.agent_cli} (fallback)"
                )
                self._on_agent_switch(old_agent, new_agent.agent_cli)
                continue

            # No more fallback agents
            self._on_log(f"[supervisor] all agents exhausted")
            if self._on_done:
                self._on_done(
                    result.exit_code,
                    result.error,
                    result.artifacts,
                    result.metadata,
                )
            return result

        # Should not reach here
        result = SupervisorResult(
            exit_code=1,
            error="All agents exhausted",
            artifacts=[],
            metadata={},
        )
        if self._on_done:
            self._on_done(
                result.exit_code,
                result.error,
                result.artifacts,
                result.metadata,
            )
        return result

    def _initialize_agent_chain(self) -> None:
        """Build ordered agent chain from agent_selection."""
        if not self._agent_selection or not self._agent_selection.agents:
            # Use default agent from config
            default_agent = AgentInstance(
                agent_id="default",
                agent_cli=self._config.agent_cli,
                config_dir=self._config.host_codex_dir,
                cli_flags="",
            )
            self._agent_chain = [default_agent]
            return

        # Build chain: [primary, fallback1, fallback2, ...]
        agents = list(self._agent_selection.agents)
        fallbacks = self._agent_selection.agent_fallbacks or {}

        # Start with first agent
        chain = [agents[0]]
        current_id = agents[0].agent_id
        visited = {current_id}

        # Follow fallback chain
        while current_id in fallbacks:
            next_id = fallbacks[current_id]
            if next_id in visited:
                # Circular fallback detected
                self._on_log(f"[supervisor] circular fallback detected, stopping chain")
                break

            next_agent = next((a for a in agents if a.agent_id == next_id), None)
            if not next_agent:
                # Invalid fallback reference
                self._on_log(f"[supervisor] invalid fallback reference: {next_id}")
                break

            chain.append(next_agent)
            visited.add(next_id)
            current_id = next_id

        self._agent_chain = chain
        self._on_log(
            f"[supervisor] agent chain: {' -> '.join(a.agent_cli for a in chain)}"
        )

    def _try_agent(self, agent: AgentInstance) -> SupervisorResult:
        """Try executing task with given agent.

        Args:
            agent: Agent instance to use

        Returns:
            SupervisorResult from this execution attempt
        """
        if self._user_stop_reason is not None:
            return self._result_for_user_stop()

        # Build agent-specific config
        agent_config = self._build_agent_config(agent)

        # Reset worker results
        self._last_exit_code = 0
        self._last_error = None
        self._last_artifacts = []
        self._last_logs = []
        self._last_container_state = {}

        # Create and run worker
        worker = DockerAgentWorker(
            config=agent_config,
            prompt=self._prompt,
            on_state=self._on_state,
            on_log=self._on_log_capture,
            on_done=self._on_worker_done,
        )
        self._current_worker = worker

        worker.run()

        self._current_worker = None

        return SupervisorResult(
            exit_code=self._last_exit_code,
            error=self._last_error,
            artifacts=self._last_artifacts,
            metadata={
                "agent_used": agent.agent_cli,
                "agent_id": agent.agent_id,
                "retry_count": self._retry_counts.get(agent.agent_id, 0),
                "total_attempts": self._total_attempts,
            },
        )

    def _result_for_user_stop(self) -> SupervisorResult:
        reason = self._user_stop_reason or "cancel"
        exit_code = 137 if reason == "kill" else 130
        return SupervisorResult(
            exit_code=exit_code,
            error=None,
            artifacts=[],
            metadata={"user_stop": reason},
        )

    def _sleep_with_cancel(self, seconds: float) -> bool:
        """Sleep but allow early-exit if a user stop is requested."""
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
            if self._user_stop_reason is not None:
                return False
            time.sleep(0.1)
        return True

    def _build_agent_config(self, agent: AgentInstance) -> DockerRunnerConfig:
        """Build DockerRunnerConfig for specific agent.

        Args:
            agent: Agent instance

        Returns:
            DockerRunnerConfig configured for this agent
        """
        # Parse agent CLI args
        agent_cli_args: list[str] = []
        if agent.cli_flags:
            import shlex

            try:
                agent_cli_args = shlex.split(agent.cli_flags)
            except ValueError:
                # Invalid flags, use empty list
                agent_cli_args = []

        config = DockerRunnerConfig(
            task_id=self._config.task_id,
            image=self._config.image,
            host_codex_dir=agent.config_dir or self._config.host_codex_dir,
            host_workdir=self._config.host_workdir,
            agent_cli=agent.agent_cli,
            container_codex_dir=self._config.container_codex_dir,
            container_workdir=self._config.container_workdir,
            auto_remove=self._config.auto_remove,
            pull_before_run=self._config.pull_before_run,
            settings_preflight_script=self._config.settings_preflight_script,
            environment_preflight_script=self._config.environment_preflight_script,
            headless_desktop_enabled=self._config.headless_desktop_enabled,
            environment_id=self._config.environment_id,
            container_settings_preflight_path=self._config.container_settings_preflight_path,
            container_environment_preflight_path=self._config.container_environment_preflight_path,
            env_vars=self._config.env_vars,
            extra_mounts=self._config.extra_mounts,
            agent_cli_args=agent_cli_args or self._config.agent_cli_args,
            gh_repo=self._config.gh_repo,
            gh_prefer_gh_cli=self._config.gh_prefer_gh_cli,
            gh_recreate_if_needed=self._config.gh_recreate_if_needed,
            gh_base_branch=self._config.gh_base_branch,
            artifact_collection_timeout_s=self._config.artifact_collection_timeout_s,
        )
        return config

    def _on_log_capture(self, log_line: str) -> None:
        """Capture log lines for error classification.

        Args:
            log_line: Log line from worker
        """
        self._last_logs.append(log_line)
        self._on_log(log_line)

    def _on_worker_done(
        self,
        exit_code: int,
        error: str | None,
        artifacts: list[str],
    ) -> None:
        """Handle worker completion.

        Args:
            exit_code: Container exit code
            error: Error message if any
            artifacts: Collected artifacts
        """
        self._last_exit_code = exit_code
        self._last_error = error
        self._last_artifacts = artifacts
        self._total_attempts += 1

        # Try to capture container state for error classification
        # Note: This is a simplified version - in full implementation,
        # we would need to capture container state before removal
        self._last_container_state = {}

    def _record_cooldown(self, agent: AgentInstance) -> None:
        """Record rate-limit cooldown for agent.

        Args:
            agent: Agent instance that was rate-limited
        """
        from agents_runner.core.agent.cooldown_manager import CooldownManager
        from agents_runner.core.agent.rate_limit import RateLimitDetector

        # Detect rate limit and extract cooldown duration
        is_rate_limited, cooldown_seconds = RateLimitDetector.detect(
            agent.agent_cli,
            self._last_exit_code,
            self._last_logs,
            self._last_container_state,
        )

        if not is_rate_limited:
            return

        # Get cooldown manager
        cooldown_mgr = CooldownManager(self._watch_states)

        # Extract reason from recent logs
        reason_lines = self._last_logs[-10:] if self._last_logs else []
        reason = "\n".join(reason_lines)[-200:]  # Limit to 200 chars

        # Record cooldown
        cooldown_mgr.set_cooldown(agent.agent_cli, cooldown_seconds, reason)

        self._on_log(
            f"[supervisor] rate-limit detected for {agent.agent_cli}, "
            f"cooldown for {cooldown_seconds}s"
        )
