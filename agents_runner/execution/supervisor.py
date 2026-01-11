"""
Task supervisor with retry, fallback, and error classification.

Supervises agent task execution with automatic retry on failure,
fallback to alternate agents, and intelligent error classification.
"""

from __future__ import annotations

import os
import re
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
from agents_runner.log_format import format_log


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


def calculate_backoff(retry_count: int, error_type: ErrorType) -> float:  # pragma: no cover
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
    - Fallback to alternate agents after any failure
    - No same-agent+config retries within a task run
    - Structured failure reasons for each attempt
    - Per agent+config cooldown on rate limit/quota errors
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
        self._total_attempts = 0
        self._attempted: set[AttemptKey] = set()
        self._attempt_history: list[dict[str, Any]] = []
        self._current_worker: DockerAgentWorker | None = None
        self._last_container_id: str | None = None
        self._last_gh_repo_root: str | None = None
        self._last_gh_base_branch: str | None = None
        self._last_gh_branch: str | None = None

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
        return self._last_container_id

    @property
    def gh_repo_root(self) -> str | None:
        """Get current worker's GitHub repo root."""
        if self._current_worker:
            return self._current_worker.gh_repo_root
        return self._last_gh_repo_root

    @property
    def gh_base_branch(self) -> str | None:
        """Get current worker's GitHub base branch."""
        if self._current_worker:
            return self._current_worker.gh_base_branch
        return self._last_gh_base_branch

    @property
    def gh_branch(self) -> str | None:
        """Get current worker's GitHub branch."""
        if self._current_worker:
            return self._current_worker.gh_branch
        return self._last_gh_branch

    def request_stop(self) -> None:
        """Request stop of current worker."""
        if self._current_worker:
            self._current_worker.request_stop()

    def request_user_cancel(self) -> None:
        """User requested graceful cancellation (terminal, no retry/fallback)."""
        if self._user_stop_reason is None:
            self._user_stop_reason = "cancel"
            self._on_log(format_log("supervisor", "none", "INFO", "user_cancel requested"))
        if self._current_worker:
            self._current_worker.request_stop()

    def request_user_kill(self) -> None:
        """User requested force kill (terminal, no retry/fallback)."""
        if self._user_stop_reason is None:
            self._user_stop_reason = "kill"
            self._on_log(format_log("supervisor", "none", "INFO", "user_kill requested"))
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
        current_agent_cli: str | None = None
        while self._current_agent_index < len(self._agent_chain):
            if self._user_stop_reason is not None:
                result = self._result_for_user_stop()
                self._on_log(format_log("supervisor", "task", "INFO", "retry skipped due to user stop"))
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        result.error,
                        result.artifacts,
                        result.metadata,
                    )
                return result

            next_agent = self._next_available_agent(start_index=self._current_agent_index)
            if next_agent is None:
                result = self._result_for_exhausted_agents()
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        result.error,
                        result.artifacts,
                        result.metadata,
                    )
                return result

            next_index, agent = next_agent
            if next_index != self._current_agent_index:
                self._current_agent_index = next_index

            if current_agent_cli and current_agent_cli != agent.agent_cli:
                self._on_agent_switch(current_agent_cli, agent.agent_cli)
            current_agent_cli = agent.agent_cli

            attempt_key = self._attempt_key(agent)
            self._attempted.add(attempt_key)

            # Try executing with current agent
            result = self._try_agent(agent)

            if self._user_stop_reason is not None:
                self._on_log(format_log("supervisor", "task", "INFO", "retry skipped due to user stop"))
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
                self._attempt_history.append(
                    {
                        "attempt_number": int(self._total_attempts),
                        "agent_cli": agent.agent_cli,
                        "agent_id": agent.agent_id,
                        "host_config_dir": attempt_key.host_config_dir,
                        "agent_cli_args": list(attempt_key.agent_cli_args),
                        "exit_code": int(result.exit_code),
                    }
                )
                final_metadata = dict(result.metadata)
                final_metadata["attempt_history"] = list(self._attempt_history)
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        result.error,
                        result.artifacts,
                        final_metadata,
                    )
                return SupervisorResult(
                    exit_code=result.exit_code,
                    error=result.error,
                    artifacts=result.artifacts,
                    metadata=final_metadata,
                )

            # Record attempt and failure reason
            failure = self._classify_failure_reason(
                exit_code=result.exit_code,
                container_state=self._last_container_state,
                logs=self._last_logs,
                exit_summary=result.error,
            )
            self._attempt_history.append(
                {
                    "attempt_number": int(self._total_attempts),
                    "agent_cli": agent.agent_cli,
                    "agent_id": agent.agent_id,
                    "host_config_dir": attempt_key.host_config_dir,
                    "agent_cli_args": list(attempt_key.agent_cli_args),
                    "exit_code": int(result.exit_code),
                    "failure_category": failure.failure_category,
                    "failure_message": failure.failure_message,
                    "matched_signals": list(failure.matched_signals),
                }
            )

            # Record cooldown if rate-limited (agent+config specific)
            if failure.failure_category == "rate_limit":
                self._record_cooldown(attempt_key, reason=failure.failure_message)

            # Select the next distinct agent+config in the fallback chain.
            self._current_agent_index += 1
            next_candidate = self._next_available_agent(start_index=self._current_agent_index)
            if next_candidate is None:
                exhausted = self._result_for_exhausted_agents(last_exit_code=result.exit_code)
                if self._on_done:
                    self._on_done(
                        exhausted.exit_code,
                        exhausted.error,
                        exhausted.artifacts,
                        exhausted.metadata,
                    )
                return exhausted

            next_attempt_number = int(self._total_attempts) + 1
            _, candidate = next_candidate
            self._on_retry(next_attempt_number, candidate.agent_cli, 0.0)
            continue

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
                self._on_log(format_log("supervisor", "task", "WARN", "circular fallback detected, stopping chain"))
                break

            next_agent = next((a for a in agents if a.agent_id == next_id), None)
            if not next_agent:
                # Invalid fallback reference
                self._on_log(format_log("supervisor", "task", "WARN", f"invalid fallback reference: {next_id}"))
                break

            chain.append(next_agent)
            visited.add(next_id)
            current_id = next_id

        self._agent_chain = chain
        self._on_log(
            format_log(
                "supervisor",
                "task",
                "INFO",
                f"agent chain: {' -> '.join(a.agent_cli for a in chain)}",
            )
        )

    def _next_available_agent(
        self, *, start_index: int
    ) -> tuple[int, AgentInstance] | None:
        for index in range(max(0, int(start_index)), len(self._agent_chain)):
            agent = self._agent_chain[index]
            key = self._attempt_key(agent)
            if key in self._attempted:
                continue
            if self._is_on_cooldown(key):
                self._on_log(
                    format_log(
                        "supervisor",
                        "cooldown",
                        "INFO",
                        f"skipping {agent.agent_cli} (agent+config) due to cooldown",
                    )
                )
                continue
            return index, agent
        return None

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

        self._last_container_id = worker.container_id
        self._last_gh_repo_root = worker.gh_repo_root
        self._last_gh_base_branch = worker.gh_base_branch
        self._last_gh_branch = worker.gh_branch
        self._current_worker = None

        return SupervisorResult(
            exit_code=self._last_exit_code,
            error=self._last_error,
            artifacts=self._last_artifacts,
            metadata={
                "agent_used": agent.agent_cli,
                "agent_id": agent.agent_id,
                "retry_count": max(0, int(self._total_attempts) - 1),
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
            desktop_cache_enabled=self._config.desktop_cache_enabled,
            container_caching_enabled=self._config.container_caching_enabled,
            cached_preflight_script=self._config.cached_preflight_script,
            environment_id=self._config.environment_id,
            gh_context_file_path=self._config.gh_context_file_path,
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

    def _attempt_key(self, agent: AgentInstance) -> AttemptKey:
        agent_cli = str(agent.agent_cli or "").strip().lower() or "codex"
        host_config_dir = os.path.expanduser(
            str(agent.config_dir or self._config.host_codex_dir or "").strip()
        )
        if host_config_dir:
            host_config_dir = os.path.abspath(host_config_dir)

        agent_cli_args = self._effective_agent_cli_args(agent)
        return AttemptKey(
            agent_cli=agent_cli,
            host_config_dir=host_config_dir,
            agent_cli_args=tuple(agent_cli_args),
        )

    def _effective_agent_cli_args(self, agent: AgentInstance) -> list[str]:
        if agent.cli_flags:
            import shlex

            try:
                return list(shlex.split(agent.cli_flags))
            except ValueError:
                return []
        return list(self._config.agent_cli_args or [])

    def _is_on_cooldown(self, attempt_key: AttemptKey) -> bool:
        from agents_runner.core.agent.cooldown_manager import CooldownManager
        from agents_runner.core.agent.keys import cooldown_key

        cooldown_mgr = CooldownManager(self._watch_states)
        key = cooldown_key(
            agent_cli=attempt_key.agent_cli,
            host_config_dir=attempt_key.host_config_dir,
            agent_cli_args=list(attempt_key.agent_cli_args),
        )
        watch_state = cooldown_mgr.check_cooldown(key)
        return bool(watch_state and watch_state.is_on_cooldown())

    def _record_cooldown(self, attempt_key: AttemptKey, *, reason: str) -> None:
        """Record a one-hour cooldown for a specific agent+config selection."""
        from agents_runner.core.agent.cooldown_manager import CooldownManager
        from agents_runner.core.agent.keys import cooldown_key

        cooldown_mgr = CooldownManager(self._watch_states)
        key = cooldown_key(
            agent_cli=attempt_key.agent_cli,
            host_config_dir=attempt_key.host_config_dir,
            agent_cli_args=list(attempt_key.agent_cli_args),
        )
        cooldown_mgr.set_cooldown(key, 3600, reason[:200])

        self._on_log(
            format_log(
                "supervisor",
                "task",
                "WARN",
                f"rate-limit detected for {attempt_key.agent_cli} (agent+config); cooldown for 3600s",
            )
        )

    def _classify_failure_reason(
        self,
        *,
        exit_code: int,
        container_state: dict[str, Any],
        logs: list[str],
        exit_summary: str | None,
    ) -> FailureReason:
        combined = "\n".join([*(logs or []), str(exit_summary or "")])
        combined_lower = combined.lower()

        # Rate limit/quota signals (minimum required set)
        rate_signals = [
            ("429", "contains: 429"),
            ("rate limit", "contains: rate limit"),
            ("quota", "contains: quota"),
            ("exceeded your copilot token usage", "contains: exceeded your Copilot token usage"),
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

    def _result_for_exhausted_agents(
        self, *, last_exit_code: int | None = None
    ) -> SupervisorResult:
        from agents_runner.core.agent.keys import cooldown_key

        attempted = [
            f"{a.get('agent_cli')}[{a.get('agent_id')}]"
            for a in self._attempt_history
            if a.get("agent_cli")
        ]

        on_cooldown: list[str] = []
        for agent in self._agent_chain:
            key = self._attempt_key(agent)
            ckey = cooldown_key(
                agent_cli=key.agent_cli,
                host_config_dir=key.host_config_dir,
                agent_cli_args=list(key.agent_cli_args),
            )
            watch_state = self._watch_states.get(ckey)
            if watch_state and watch_state.is_on_cooldown() and ckey:
                until = getattr(watch_state, "cooldown_until", None)
                until_s = until.isoformat() if until else "unknown"
                on_cooldown.append(f"{agent.agent_cli}[{agent.agent_id}] until {until_s}")

        parts = []
        if attempted:
            parts.append("attempted: " + ", ".join(attempted))
        if on_cooldown:
            parts.append("on cooldown: " + ", ".join(on_cooldown))
        message = "all agents unavailable"
        if parts:
            message = message + " (" + " | ".join(parts) + ")"
        return SupervisorResult(
            exit_code=int(last_exit_code or 1),
            error=message,
            artifacts=list(self._last_artifacts or []),
            metadata={
                "attempt_history": list(self._attempt_history),
                "total_attempts": int(self._total_attempts),
            },
        )
