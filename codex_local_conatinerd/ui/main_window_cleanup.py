from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import threading
import time

from datetime import datetime
from datetime import timezone
from uuid import uuid4
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtCore import Slot

from PySide6.QtWidgets import QMessageBox

from codex_local_conatinerd.environments import managed_repos_dir
from codex_local_conatinerd.environments import SYSTEM_ENV_ID
from codex_local_conatinerd.ui.bridges import HostCleanupBridge
from codex_local_conatinerd.ui.task_model import Task


class _MainWindowCleanupMixin:
    @staticmethod
    def _repo_scripts_dir() -> str:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

    @classmethod
    def _script_path(cls, filename: str) -> str:
        return os.path.join(cls._repo_scripts_dir(), str(filename or "").strip())

    @staticmethod
    def _stream_cmd(
        args: list[str],
        log: Callable[[str], None],
        stop: threading.Event,
        *,
        timeout_s: float | None = None,
    ) -> tuple[int, list[str]]:
        log(f"$ {_MainWindowCleanupMixin._format_cmd(args)}")
        output_lines: list[str] = []
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as exc:
            return 1, [str(exc)]

        assert proc.stdout is not None
        for raw in proc.stdout:
            if stop.is_set():
                try:
                    proc.terminate()
                except Exception:
                    pass
                break
            line = str(raw or "").rstrip("\n")
            if line:
                log(line)
                output_lines.append(line)

        try:
            exit_code = int(proc.wait(timeout=timeout_s))
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            exit_code = 1
        return exit_code, output_lines

    def _on_settings_clean_docker(self) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return
        if self._docker_cleanup_task_id is not None:
            QMessageBox.information(self, "Clean Docker", "A Docker cleanup is already running.")
            return

        self._docker_cleanup_task_id = self._start_cleanup_task(
            kind="docker",
            label="Clean Docker",
            target=str(self._settings_data.get("host_workdir") or os.getcwd()),
            runner=self._run_docker_prune,
        )
        self._sync_settings_clean_state()
    def _on_settings_clean_git_folders(self) -> None:
        if self._git_cleanup_task_id is not None:
            QMessageBox.information(self, "Clean Git Folders", "A git cleanup is already running.")
            return

        target = managed_repos_dir(data_dir=os.path.dirname(self._state_path))
        self._git_cleanup_task_id = self._start_cleanup_task(
            kind="git",
            label="Clean Git Folders",
            target=target,
            runner=self._run_clean_git_folders,
        )
        self._sync_settings_clean_state()


    def _on_settings_clean_all(self) -> None:
        if self._clean_all_queue:
            QMessageBox.information(self, "Clean All", "A Clean All run is already in progress.")
            return
        if self._docker_cleanup_task_id is not None or self._git_cleanup_task_id is not None:
            QMessageBox.information(
                self,
                "Clean All",
                "Finish the currently running cleanup first.",
            )
            return
        docker_task_id = self._start_cleanup_task(
            kind="docker",
            label="Clean Docker",
            target=str(self._settings_data.get("host_workdir") or os.getcwd()),
            runner=self._run_docker_prune,
        )
        git_target = managed_repos_dir(data_dir=os.path.dirname(self._state_path))
        git_task_id = self._start_cleanup_task(
            kind="git",
            label="Clean Git Folders",
            target=git_target,
            runner=self._run_clean_git_folders,
            defer_start=True,
        )
        self._docker_cleanup_task_id = docker_task_id
        self._git_cleanup_task_id = git_task_id
        self._clean_all_queue = [docker_task_id, git_task_id]
        self._sync_settings_clean_state()
        self._start_next_clean_all_step()


    def _sync_settings_clean_state(self) -> None:
        self._settings.set_clean_state(
            docker_busy=self._docker_cleanup_task_id is not None,
            git_busy=self._git_cleanup_task_id is not None,
            all_busy=bool(self._clean_all_queue),
        )


    def _start_next_clean_all_step(self) -> None:
        while self._clean_all_queue:
            task_id = str(self._clean_all_queue[0] or "").strip()
            if not task_id:
                self._clean_all_queue.pop(0)
                continue
            if task_id in self._cleanup_threads:
                return
            if task_id not in self._cleanup_pending:
                self._clean_all_queue.pop(0)
                continue
            self._begin_cleanup_task(task_id)
            return
        self._sync_settings_clean_state()


    def _format_cmd(args: list[str]) -> str:
        return " ".join(shlex.quote(str(a)) for a in args)


    def _start_cleanup_task(
        self,
        *,
        kind: str,
        label: str,
        target: str,
        runner: Callable[[Callable[[str], None], threading.Event], tuple[int, str]],
        defer_start: bool = False,
    ) -> str:
        task_id = uuid4().hex[:10]
        queued = bool(defer_start)
        task = Task(
            task_id=task_id,
            prompt=str(label or "Cleanup").strip(),
            image="",
            host_workdir=str(target or "").strip(),
            host_codex_dir="",
            created_at_s=time.time(),
            environment_id=SYSTEM_ENV_ID,
            status="queued" if queued else "running",
        )
        if not queued:
            task.started_at = datetime.now(tz=timezone.utc)
        self._tasks[task_id] = task
        self._dashboard.upsert_task(task, stain="slate")
        self._schedule_save()

        self._cleanup_pending[task_id] = (str(kind or "").strip().lower(), runner)
        if defer_start:
            self._on_task_log(task_id, "[queue] waiting for previous cleanup step…")
            self._show_dashboard()
            return task_id
        self._begin_cleanup_task(task_id)
        return task_id


    def _begin_cleanup_task(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        pending = self._cleanup_pending.pop(task_id, None)
        if pending is None:
            return
        kind, runner = pending
        task = self._tasks.get(task_id)
        if task is not None:
            if task.started_at is None:
                task.started_at = datetime.now(tz=timezone.utc)
            task.status = "running"
            self._dashboard.upsert_task(task, stain="slate")

        bridge = HostCleanupBridge(task_id=task_id, kind=kind, runner=runner)
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.log.connect(
            lambda line, tid=task_id: self._on_task_log(tid, str(line or "")),
            Qt.QueuedConnection,
        )
        bridge.done.connect(
            lambda exit_code, output, tid=task_id, k=kind: self._on_cleanup_done(
                tid, k, int(exit_code), str(output or "")
            ),
            Qt.QueuedConnection,
        )

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._cleanup_threads[task_id] = thread
        self._cleanup_bridges[task_id] = bridge

        thread.start()
        self._show_dashboard()


    def _finalize_cleanup_task(self, task_id: str, exit_code: int, *, error: str | None = None) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.exit_code = int(exit_code)
        task.error = str(error) if error else None
        task.status = "done" if int(exit_code) == 0 else "failed"
        task.finished_at = datetime.now(tz=timezone.utc)
        self._dashboard.upsert_task(task)
        self._details.update_task(task)
        self._schedule_save()


    def _on_cleanup_done(self, task_id: str, kind: str, exit_code: int, output: str) -> None:
        kind = str(kind or "").strip().lower()
        self._cleanup_threads.pop(task_id, None)
        self._cleanup_bridges.pop(task_id, None)

        output = str(output or "").strip()
        if not output:
            output = f"Command exited with code {int(exit_code)}."

        self._finalize_cleanup_task(task_id, int(exit_code))

        if kind == "docker":
            self._docker_cleanup_task_id = None
            title = "Docker cleaned" if int(exit_code) == 0 else "Docker cleanup failed"
        else:
            self._git_cleanup_task_id = None
            title = "Git folders cleaned" if int(exit_code) == 0 else "Git folders cleanup failed"

        continuing = False
        if self._clean_all_queue and self._clean_all_queue[0] == task_id:
            self._clean_all_queue.pop(0)
            continuing = bool(self._clean_all_queue)

        self._sync_settings_clean_state()

        if continuing:
            self._start_next_clean_all_step()
            return

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(title)
        if kind == "docker":
            box.setInformativeText(
                "Runs Docker commands without sudo. This may fail if Docker is not configured for your user."
            )
        else:
            box.setInformativeText(
                "Deletes GUI-managed folders without sudo. This may fail if the files are owned by root."
            )
        box.setDetailedText(output)
        box.setIcon(QMessageBox.Icon.Information if int(exit_code) == 0 else QMessageBox.Icon.Critical)
        box.exec()
        if self._clean_all_queue:
            self._start_next_clean_all_step()


    def _run_docker_prune(
        self,
        log: Callable[[str], None],
        stop: threading.Event,
    ) -> tuple[int, str]:
        script = self._script_path("clean-docker.sh")
        if not os.path.exists(script):
            msg = f"Missing script: {script}"
            log(msg)
            return 1, msg
        exit_code, lines = self._stream_cmd(["bash", script], log, stop, timeout_s=None)
        output = "\n".join(lines).strip() or f"Command exited with code {exit_code}."
        return int(exit_code), output


    def _run_clean_git_folders(
        self,
        log: Callable[[str], None],
        stop: threading.Event,
    ) -> tuple[int, str]:
        data_dir = os.path.dirname(self._state_path)
        target = managed_repos_dir(data_dir=data_dir)
        script = self._script_path("clean-git-managed-repos.sh")
        if not os.path.exists(script):
            msg = f"Missing script: {script}"
            log(msg)
            return 1, msg
        if stop.is_set():
            return 1, "Cancelled."
        exit_code, lines = self._stream_cmd(["bash", script, target], log, stop, timeout_s=None)
        output = "\n".join(lines).strip() or f"Command exited with code {exit_code}."
        return int(exit_code), output
