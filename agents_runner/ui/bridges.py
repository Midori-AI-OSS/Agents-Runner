from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from agents_runner.docker_runner import DockerAgentWorker
from agents_runner.docker_runner import DockerPreflightWorker
from agents_runner.docker_runner import DockerRunnerConfig
from agents_runner.environments.model import AgentSelection
from agents_runner.execution.supervisor import SupervisorConfig
from agents_runner.execution.supervisor import TaskSupervisor


class TaskRunnerBridge(QObject):
    state = Signal(str, dict)  # task_id, state
    log = Signal(str, str)  # task_id, log line
    done = Signal(
        str, int, object, list, dict
    )  # task_id, exit_code, error, artifacts, metadata
    retry_attempt = Signal(
        str, int, str, float
    )  # task_id, attempt_number, agent, delay_seconds
    agent_switched = Signal(str, str, str)  # task_id, from_agent, to_agent

    def __init__(
        self,
        task_id: str,
        config: DockerRunnerConfig,
        prompt: str = "",
        mode: str = "codex",
        agent_selection: AgentSelection | None = None,
        use_supervisor: bool = True,
        watch_states: dict | None = None,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self._use_supervisor = use_supervisor

        if mode == "preflight":
            self._worker = DockerPreflightWorker(
                config=config,
                on_state=lambda state: self.state.emit(self.task_id, state),
                on_log=lambda line: self.log.emit(self.task_id, line),
                on_done=lambda code, err: self.done.emit(
                    self.task_id, code, err, [], {}
                ),
            )
        elif use_supervisor and mode != "preflight":
            # Use supervisor for agent runs
            supervisor_config = SupervisorConfig(
                max_retries_per_agent=0,
                enable_fallback=True,
            )
            self._worker = TaskSupervisor(
                config=config,
                prompt=prompt,
                agent_selection=agent_selection,
                supervisor_config=supervisor_config,
                on_state=lambda state: self.state.emit(self.task_id, state),
                on_log=lambda line: self.log.emit(self.task_id, line),
                on_retry=lambda attempt, agent, delay: self.retry_attempt.emit(
                    self.task_id, attempt, agent, delay
                ),
                on_agent_switch=lambda from_agent, to_agent: self.agent_switched.emit(
                    self.task_id, from_agent, to_agent
                ),
                on_done=lambda code, err, artifacts, metadata: self.done.emit(
                    self.task_id, code, err, artifacts, metadata
                ),
                watch_states=watch_states or {},
            )
        else:
            # Legacy mode without supervisor
            self._worker = DockerAgentWorker(
                config=config,
                prompt=prompt,
                on_state=lambda state: self.state.emit(self.task_id, state),
                on_log=lambda line: self.log.emit(self.task_id, line),
                on_done=lambda code, err, artifacts: self.done.emit(
                    self.task_id, code, err, artifacts, {}
                ),
            )

    @property
    def container_id(self) -> str | None:
        return self._worker.container_id

    @property
    def gh_repo_root(self) -> str | None:
        return getattr(self._worker, "gh_repo_root", None)

    @property
    def gh_base_branch(self) -> str | None:
        return getattr(self._worker, "gh_base_branch", None)

    @property
    def gh_branch(self) -> str | None:
        return getattr(self._worker, "gh_branch", None)

    @Slot()
    def request_stop(self) -> None:
        self._worker.request_stop()

    @Slot()
    def request_user_cancel(self) -> None:
        request = getattr(self._worker, "request_user_cancel", None)
        if callable(request):
            request()
            return
        self._worker.request_stop()

    @Slot()
    def request_user_kill(self) -> None:
        request = getattr(self._worker, "request_user_kill", None)
        if callable(request):
            request()
            return
        request_kill = getattr(self._worker, "request_kill", None)
        if callable(request_kill):
            request_kill()
            return
        self._worker.request_stop()

    @Slot()
    def run(self) -> None:
        try:
            self._worker.run()
        except Exception as exc:
            # Ensure done signal is always emitted, even on unhandled exceptions
            # This guarantees finalization (including cleanup) always runs
            import traceback

            error_msg = f"Worker exception: {exc}\n{traceback.format_exc()}"
            self.done.emit(self.task_id, 1, error_msg, [], {})
