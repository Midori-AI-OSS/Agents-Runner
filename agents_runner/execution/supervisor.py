"""
Task supervisor with retry, fallback, and error classification.

Supervises agent task execution with automatic retry on failure,
fallback to alternate agents, and intelligent error classification.
"""

from __future__ import annotations

import os
from typing import Any
from typing import Callable
from typing import Literal

from agents_runner.agent_cli import additional_config_mounts
from agents_runner.agent_cli import default_host_config_dir
from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker_runner import DockerAgentWorker
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection
from agents_runner.execution.supervisor_errors import classify_failure_reason
from agents_runner.execution.supervisor_types import AttemptKey
from agents_runner.execution.supervisor_types import SupervisorConfig
from agents_runner.execution.supervisor_types import SupervisorResult
from agents_runner.log_format import format_log
from agents_runner.prompts import RetryContext
from agents_runner.prompts import build_task_prompt


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
        on_done: Callable[[int, str | None, list[str], dict[str, Any]], None]
        | None = None,
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
            self._on_log(
                format_log("supervisor", "none", "INFO", "user_cancel requested")
            )
        if self._current_worker:
            self._current_worker.request_stop()

    def request_user_kill(self) -> None:
        """User requested force kill (terminal, no retry/fallback)."""
        if self._user_stop_reason is None:
            self._user_stop_reason = "kill"
            self._on_log(
                format_log("supervisor", "none", "INFO", "user_kill requested")
            )
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
                self._on_log(
                    format_log(
                        "supervisor", "task", "INFO", "retry skipped due to user stop"
                    )
                )
                if self._on_done:
                    self._on_done(
                        result.exit_code,
                        result.error,
                        result.artifacts,
                        result.metadata,
                    )
                return result

            next_agent = self._next_available_agent(
                start_index=self._current_agent_index
            )
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
                self._on_log(
                    format_log(
                        "supervisor", "task", "INFO", "retry skipped due to user stop"
                    )
                )
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
            failure = classify_failure_reason(
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
            next_candidate = self._next_available_agent(
                start_index=self._current_agent_index
            )
            if next_candidate is None:
                exhausted = self._result_for_exhausted_agents(
                    last_exit_code=result.exit_code
                )
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
                config_dir=self._config.host_config_dir,
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
                self._on_log(
                    format_log(
                        "supervisor",
                        "task",
                        "WARN",
                        "circular fallback detected, stopping chain",
                    )
                )
                break

            next_agent = next((a for a in agents if a.agent_id == next_id), None)
            if not next_agent:
                # Invalid fallback reference
                self._on_log(
                    format_log(
                        "supervisor",
                        "task",
                        "WARN",
                        f"invalid fallback reference: {next_id}",
                    )
                )
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

        attempt_number = int(self._total_attempts) + 1
        prompt_for_attempt = self._prompt
        if attempt_number > 1:
            previous = self._attempt_history[-1] if self._attempt_history else {}
            prompt_for_attempt = build_task_prompt(
                self._prompt,
                retry_context=RetryContext(
                    attempt_number=attempt_number,
                    total_configured_attempts=len(self._agent_chain) or None,
                    previous_agent=str(previous.get("agent_cli") or "unknown"),
                    previous_config=str(previous.get("host_config_dir") or "unknown"),
                    previous_failure_category=str(
                        previous.get("failure_category") or "unknown"
                    ),
                    previous_failure_summary=str(
                        previous.get("failure_message") or "unknown"
                    ),
                ),
            )

        # Build agent-specific config
        agent_config = self._build_agent_config(agent)
        config_mount_sources = [str(agent_config.host_config_dir or "").strip()]
        for mount_spec in additional_config_mounts(
            agent.agent_cli, agent_config.host_config_dir
        ):
            src = str(mount_spec or "").split(":", 1)[0].strip()
            if src:
                config_mount_sources.append(src)
        config_mount_sources = [p for p in dict.fromkeys(config_mount_sources) if p]
        preview = ", ".join(config_mount_sources[:6])
        if len(config_mount_sources) > 6:
            preview = f"{preview}, …(+{len(config_mount_sources) - 6})"
        self._on_log(
            format_log(
                "supervisor",
                "attempt",
                "INFO",
                f"selected agent={agent.agent_cli} config={agent_config.host_config_dir} config_mounts=[{preview}]",
            )
        )

        # Reset worker results
        self._last_exit_code = 0
        self._last_error = None
        self._last_artifacts = []
        self._last_logs = []
        self._last_container_state = {}

        # Create and run worker
        worker = DockerAgentWorker(
            config=agent_config,
            prompt=prompt_for_attempt,
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
        host_config_dir = self._resolve_host_config_dir(agent)
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
            host_config_dir=host_config_dir,
            host_workdir=self._config.host_workdir,
            agent_cli=agent.agent_cli,
            container_config_dir=self._config.container_config_dir,
            container_workdir=self._config.container_workdir,
            auto_remove=self._config.auto_remove,
            pull_before_run=self._config.pull_before_run,
            settings_preflight_script=self._config.settings_preflight_script,
            environment_preflight_script=self._config.environment_preflight_script,
            headless_desktop_enabled=self._config.headless_desktop_enabled,
            desktop_cache_enabled=self._config.desktop_cache_enabled,
            container_caching_enabled=self._config.container_caching_enabled,
            cache_system_preflight_enabled=self._config.cache_system_preflight_enabled,
            cache_settings_preflight_enabled=self._config.cache_settings_preflight_enabled,
            cache_environment_preflight_enabled=self._config.cache_environment_preflight_enabled,
            environment_id=self._config.environment_id,
            gh_context_file_path=self._config.gh_context_file_path,
            container_settings_preflight_path=self._config.container_settings_preflight_path,
            container_environment_preflight_path=self._config.container_environment_preflight_path,
            env_vars=self._config.env_vars,
            extra_mounts=self._config.extra_mounts,
            ports=self._config.ports,
            agent_cli_args=agent_cli_args or self._config.agent_cli_args,
            gh_repo=self._config.gh_repo,
            gh_prefer_gh_cli=self._config.gh_prefer_gh_cli,
            gh_recreate_if_needed=self._config.gh_recreate_if_needed,
            gh_base_branch=self._config.gh_base_branch,
            artifact_collection_timeout_s=self._config.artifact_collection_timeout_s,
        )
        return config

    def _resolve_host_config_dir(self, agent: AgentInstance) -> str:
        configured = os.path.expanduser(str(agent.config_dir or "").strip())
        codex_default: str | None = None
        if str(self._config.agent_cli or "").strip().lower() == "codex":
            codex_default = self._config.host_config_dir
        host_config_dir = configured or default_host_config_dir(
            agent.agent_cli, codex_default=codex_default
        )
        host_config_dir = str(host_config_dir or "").strip()
        if host_config_dir:
            host_config_dir = os.path.abspath(host_config_dir)
        return host_config_dir

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
        host_config_dir = self._resolve_host_config_dir(agent)

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
                on_cooldown.append(
                    f"{agent.agent_cli}[{agent.agent_id}] until {until_s}"
                )

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
