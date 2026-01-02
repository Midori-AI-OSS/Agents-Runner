from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from agents_runner.docker_runner import DockerAgentWorker
from agents_runner.docker_runner import DockerPreflightWorker
from agents_runner.docker_runner import DockerRunnerConfig
from agents_runner.gh_management import prepare_github_repo_for_task


class TaskRunnerBridge(QObject):
    state = Signal(dict)
    log = Signal(str)
    done = Signal(int, object)

    def __init__(self, task_id: str, config: DockerRunnerConfig, prompt: str = "", mode: str = "codex") -> None:
        super().__init__()
        self.task_id = task_id
        if mode == "preflight":
            self._worker = DockerPreflightWorker(
                config=config,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err),
            )
        else:
            self._worker = DockerAgentWorker(
                config=config,
                prompt=prompt,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err),
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

    def run(self) -> None:
        self._worker.run()
