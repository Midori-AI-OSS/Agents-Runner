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
    state = Signal(dict)
    log = Signal(str)
    done = Signal(int, object, list, dict)  # Added dict for metadata
    retry_attempt = Signal(int, str, float)  # retry_count, agent, delay
    agent_switched = Signal(str, str)  # from_agent, to_agent

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
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err, [], {}),
            )
        elif use_supervisor and mode != "preflight":
            # Use supervisor for agent runs
            supervisor_config = SupervisorConfig(
                max_retries_per_agent=3,
                enable_fallback=True,
            )
            self._worker = TaskSupervisor(
                config=config,
                prompt=prompt,
                agent_selection=agent_selection,
                supervisor_config=supervisor_config,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_retry=self.retry_attempt.emit,
                on_agent_switch=self.agent_switched.emit,
                on_done=self.done.emit,
                watch_states=watch_states or {},
            )
        else:
            # Legacy mode without supervisor
            self._worker = DockerAgentWorker(
                config=config,
                prompt=prompt,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err, artifacts: self.done.emit(
                    code, err, artifacts, {}
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

    def run(self) -> None:
        self._worker.run()
