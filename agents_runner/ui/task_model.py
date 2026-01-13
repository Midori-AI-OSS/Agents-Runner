from __future__ import annotations

import time
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from agents_runner.environments import GH_MANAGEMENT_NONE
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.ui.utils import _format_duration


@dataclass
class Task:
    task_id: str
    prompt: str
    image: str
    host_workdir: str
    host_codex_dir: str
    created_at_s: float
    environment_id: str = ""
    status: str = "queued"
    exit_code: int | None = None
    error: str | None = None
    container_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    logs: list[str] = field(default_factory=list)
    gh_management_mode: str = GH_MANAGEMENT_NONE
    gh_use_host_cli: bool = True
    gh_repo_root: str = ""
    gh_base_branch: str = ""
    gh_branch: str = ""
    gh_pr_url: str = ""
    gh_pr_metadata_path: str = ""
    gh_management_locked: bool = False
    workspace_type: str = WORKSPACE_NONE
    git: dict[str, object] | None = None
    agent_cli: str = ""
    agent_instance_id: str = ""
    agent_cli_args: str = ""
    headless_desktop_enabled: bool = False
    novnc_url: str = ""
    vnc_password: str = ""
    desktop_display: str = ""
    artifacts: list[str] = field(default_factory=list)
    attempt_history: list[dict[str, object]] = field(default_factory=list)

    def last_nonblank_log_line(self) -> str:
        for line in reversed(self.logs):
            text = str(line or "").strip()
            if text:
                return text
        return ""

    def elapsed_seconds(self, now_s: float | None = None) -> float | None:
        created_s = float(self.created_at_s or 0.0)
        if created_s <= 0.0:
            if (
                self.started_at
                and self.finished_at
                and self.finished_at > self.started_at
            ):
                return (self.finished_at - self.started_at).total_seconds()
            return None
        finished = self.finished_at
        if finished is not None and finished.year < 1970:
            finished = None
        if finished is not None:
            try:
                end_s = float(finished.timestamp())
            except Exception:
                end_s = float(now_s if now_s is not None else time.time())
        else:
            end_s = float(now_s if now_s is not None else time.time())
        return max(0.0, end_s - created_s)

    def is_interactive_run(self) -> bool:
        container_id = str(self.container_id or "")
        return container_id.startswith("codex-gui-it-")

    def prompt_one_line(self) -> str:
        line = (self.prompt or "").strip().splitlines()[0] if self.prompt else ""
        if line:
            return line
        if self.is_interactive_run():
            return "Interactive"
        return "(empty prompt)"

    def info_one_line(self) -> str:
        if self.error:
            return self.error.replace("\n", " ").strip()
        duration = self.elapsed_seconds()
        if self.exit_code is None:
            if self.is_active():
                last_line = self.last_nonblank_log_line()
                if last_line:
                    return last_line
                return f"elapsed {_format_duration(duration)}"
            return ""
        if self.exit_code == 0:
            last_line = self.last_nonblank_log_line()
            dur = _format_duration(duration)
            if last_line and dur != "—":
                return f"{last_line} • {dur}"
            if last_line:
                return last_line
            return f"ok • {dur}"
        return f"exit {self.exit_code} • {_format_duration(duration)}"

    def is_active(self) -> bool:
        return (self.status or "").lower() in {
            "queued",
            "pulling",
            "cloning",
            "created",
            "running",
            "starting",
            "cleaning",
        }

    def is_done(self) -> bool:
        status = (self.status or "").lower()
        if status in {"done", "cancelled", "killed"}:
            return True
        return status == "exited" and self.exit_code == 0

    def is_failed(self) -> bool:
        status = (self.status or "").lower()
        if status in {"cancelled", "killed"}:
            return False
        if status in {"failed", "error", "dead"}:
            return True
        return status == "exited" and self.exit_code not in (None, 0)

    def requires_git_metadata(self) -> bool:
        """
        Returns True if this task requires git metadata (PR creation, git context, etc.).
        Only cloned workspace environments require git metadata.
        """
        return self.workspace_type == WORKSPACE_CLONED


def _task_display_status(task: Task) -> str:
    status = (task.status or "").lower()
    if status == "done":
        return "Done"
    if status == "cancelled":
        return "Cancelled"
    if status == "killed":
        return "Killed"
    if status in {"failed", "error"}:
        return "Failed"
    if status == "pulling":
        return "Pulling"
    if status == "cloning":
        return "Cloning"
    if status == "running":
        return "Running"
    if status == "created":
        return "Created"
    if status == "queued":
        return "Queued"
    if status == "starting":
        return "Starting"
    if status == "paused":
        return "Paused"
    if status == "restarting":
        return "Restarting"
    if status == "removing":
        return "Removing"
    if status == "exited" and task.exit_code == 0:
        return "Done"
    if status == "exited" and task.exit_code is not None:
        return f"Exit {task.exit_code}"
    if status == "unknown":
        return "Unknown"
    return status.title() if status else "—"
