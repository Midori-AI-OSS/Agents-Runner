from __future__ import annotations

import os
import shutil
import subprocess
import threading

from datetime import datetime
from datetime import timezone

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread

from PySide6.QtWidgets import QMessageBox

from codex_local_conatinerd.persistence import default_state_path
from codex_local_conatinerd.environments import managed_repos_dir
from codex_local_conatinerd.ui.bridges import DockerPruneBridge
from codex_local_conatinerd.ui.bridges import HostCleanupBridge


class _MainWindowCleanupMixin:
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
        self._clean_all_queue = ["docker", "git"]
        self._sync_settings_clean_state()
        self._start_next_clean_all_step()


    def _sync_settings_clean_state(self) -> None:
        self._settings.set_clean_state(
            docker_busy=self._docker_cleanup_task_id is not None,
            git_busy=self._git_cleanup_task_id is not None,
            all_busy=bool(self._clean_all_queue),
        )


    def _start_next_clean_all_step(self) -> None:
        if not self._clean_all_queue:
            self._sync_settings_clean_state()
            return
        kind = str(self._clean_all_queue[0] or "").strip().lower()
        if kind == "docker":
            self._on_settings_clean_docker()
            return
        if kind == "git":
            self._on_settings_clean_git_folders()
            return
        self._clean_all_queue.pop(0)
        self._start_next_clean_all_step()


    def _format_cmd(args: list[str]) -> str:
        return " ".join(shlex.quote(str(a)) for a in args)


    def _start_cleanup_task(
        self,
        *,
        kind: str,
        label: str,
        target: str,
        runner: Callable[[Callable[[str], None], threading.Event], tuple[int, str]],
    ) -> str:
        task_id = uuid4().hex[:10]
        task = Task(
            task_id=task_id,
            prompt=str(label or "Cleanup").strip(),
            image="",
            host_workdir=str(target or "").strip(),
            host_codex_dir="",
            created_at_s=time.time(),
            status="cleaning",
        )
        task.started_at = datetime.now(tz=timezone.utc)
        self._tasks[task_id] = task
        self._dashboard.upsert_task(task, stain="slate")
        self._schedule_save()

        bridge = HostCleanupBridge(runner)
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.log.connect(lambda line, tid=task_id: self.host_log.emit(tid, line), Qt.QueuedConnection)
        bridge.done.connect(
            lambda code, output, tid=task_id, k=kind: self._on_cleanup_done(tid, k, int(code), str(output or "")),
            Qt.QueuedConnection,
        )

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._cleanup_threads[task_id] = thread
        self._cleanup_bridges[task_id] = bridge

        thread.start()
        self._show_dashboard()
        return task_id


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

        self._sync_settings_clean_state()

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(title)
        box.setDetailedText(output)
        box.setIcon(QMessageBox.Icon.Information if int(exit_code) == 0 else QMessageBox.Icon.Critical)
        box.exec()

        if self._clean_all_queue and self._clean_all_queue[0] == kind:
            self._clean_all_queue.pop(0)
            self._sync_settings_clean_state()
            self._start_next_clean_all_step()


    def _run_docker_prune(
        self,
        log: Callable[[str], None],
        stop: threading.Event,
    ) -> tuple[int, str]:
        docker_args = ["docker", "system", "prune", "-f", "-a"]
        args = ["sudo", "-n", *docker_args] if shutil.which("sudo") else docker_args
        log(f"$ {self._format_cmd(args)}")
        output_lines: list[str] = []
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as exc:
            return 1, str(exc)
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
            exit_code = int(proc.wait(timeout=60.0))
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            exit_code = 1
        output = "\n".join(output_lines).strip()
        if not output:
            output = f"Command exited with code {exit_code}."
        return exit_code, output


    def _run_clean_git_folders(
        self,
        log: Callable[[str], None],
        stop: threading.Event,
    ) -> tuple[int, str]:
        data_dir = os.path.dirname(self._state_path)
        target = managed_repos_dir(data_dir=data_dir)
        log(f"Target: {target}")

        target_real = os.path.realpath(target)
        data_real = os.path.realpath(data_dir)
        if not (target_real == data_real or target_real.startswith(data_real + os.sep)):
            msg = f"Refusing to delete unexpected path: {target_real}"
            log(msg)
            return 1, msg

        if not os.path.exists(target):
            msg = "Nothing to clean."
            log(msg)
            return 0, msg

        if stop.is_set():
            return 1, "Cancelled."

        args = ["sudo", "-n", "rm", "-rf", target] if shutil.which("sudo") else ["rm", "-rf", target]
        log(f"$ {self._format_cmd(args)}")
        try:
            proc = subprocess.run(args, capture_output=True, text=True, check=False)
        except Exception as exc:
            return 1, str(exc)

        output = "\n".join([str(proc.stdout or "").strip(), str(proc.stderr or "").strip()]).strip()
        if not output:
            output = f"Command exited with code {proc.returncode}."
        return int(proc.returncode), output
