from __future__ import annotations

import shutil
import subprocess
import threading
from typing import Callable

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


class DockerPruneBridge(QObject):
    done = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()

    def run(self) -> None:
        docker_args = ["docker", "system", "prune", "-f", "-a"]
        args: list[str]
        if shutil.which("sudo"):
            args = ["sudo", "-n", *docker_args]
        else:
            args = docker_args

        try:
            proc = subprocess.run(args, capture_output=True, text=True, check=False)
        except Exception as exc:
            self.done.emit(1, str(exc))
            return

        output = "\n".join([str(proc.stdout or "").strip(), str(proc.stderr or "").strip()]).strip()
        if not output:
            output = f"Command exited with code {proc.returncode}."
        self.done.emit(int(proc.returncode), output)


class HostCleanupBridge(QObject):
    log = Signal(str)
    done = Signal(int, str)

    def __init__(
        self,
        *,
        task_id: str,
        kind: str,
        runner: Callable[[Callable[[str], None], threading.Event], tuple[int, str]],
    ) -> None:
        super().__init__()
        self.task_id = str(task_id or "").strip()
        self.kind = str(kind or "").strip()
        self._runner = runner
        self._stop = threading.Event()

    @Slot()
    def request_stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            exit_code, output = self._runner(self.log.emit, self._stop)
        except Exception as exc:
            self.done.emit(1, str(exc))
            return
        self.done.emit(int(exit_code), str(output or "").strip())
