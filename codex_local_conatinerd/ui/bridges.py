from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from codex_local_conatinerd.docker_runner import DockerCodexWorker
from codex_local_conatinerd.docker_runner import DockerPreflightWorker
from codex_local_conatinerd.docker_runner import DockerRunnerConfig


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
            self._worker = DockerCodexWorker(
                config=config,
                prompt=prompt,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err),
            )

    @property
    def container_id(self) -> str | None:
        return self._worker.container_id

    @Slot()
    def request_stop(self) -> None:
        self._worker.request_stop()

    def run(self) -> None:
        self._worker.run()
