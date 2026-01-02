from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from agents_runner.docker_runner import DockerAgentWorker
from agents_runner.docker_runner import DockerPreflightWorker
from agents_runner.docker_runner import DockerRunnerConfig
from agents_runner.gh_management import ensure_github_clone
from agents_runner.gh_management import is_git_repo
from agents_runner.gh_management import plan_repo_task
from agents_runner.gh_management import prepare_branch_for_task
from agents_runner.gh_management import GhManagementError


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


class GhManagementBridge(QObject):
    log = Signal(str)
    done = Signal(bool, object)

    def __init__(
        self,
        *,
        task_id: str,
        repo: str,
        dest_dir: str,
        prefer_gh: bool = True,
        recreate_if_needed: bool = True,
        base_branch: str = "",
    ) -> None:
        super().__init__()
        self._task_id = str(task_id or "").strip()
        self._repo = str(repo or "").strip()
        self._dest_dir = str(dest_dir or "").strip()
        self._prefer_gh = bool(prefer_gh)
        self._recreate_if_needed = bool(recreate_if_needed)
        self._base_branch = str(base_branch or "").strip()
        self._stop_requested = False

    @Slot()
    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        if self._stop_requested:
            self.done.emit(False, "cancelled")
            return
        try:
            self.log.emit(f"[gh] cloning {self._repo} -> {self._dest_dir}")
            ensure_github_clone(
                self._repo,
                self._dest_dir,
                prefer_gh=self._prefer_gh,
                recreate_if_needed=self._recreate_if_needed,
            )
            result: dict[str, str] = {"repo_root": "", "base_branch": "", "branch": ""}
            if is_git_repo(self._dest_dir):
                plan = plan_repo_task(
                    self._dest_dir,
                    task_id=self._task_id,
                    base_branch=self._base_branch or None,
                )
                if plan is not None:
                    self.log.emit(f"[gh] creating branch {plan.branch} (base {plan.base_branch})")
                    base_branch, branch = prepare_branch_for_task(
                        plan.repo_root,
                        branch=plan.branch,
                        base_branch=plan.base_branch,
                    )
                    result = {"repo_root": plan.repo_root, "base_branch": base_branch, "branch": branch}
                else:
                    self.log.emit("[gh] not a git repo; skipping branch/PR")
            else:
                self.log.emit("[gh] not a git repo; skipping branch/PR")
            self.done.emit(True, result)
        except GhManagementError as exc:
            self.done.emit(False, str(exc))
        except Exception as exc:
            self.done.emit(False, str(exc))
