from __future__ import annotations

import os
import shlex
import subprocess
import time

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.gh_management import GhManagementError
from agents_runner.gh_management import prepare_github_repo_for_task
from agents_runner.log_format import format_log
from agents_runner.pr_metadata import ensure_pr_metadata_file
from agents_runner.pr_metadata import pr_metadata_container_path
from agents_runner.pr_metadata import pr_metadata_host_path
from agents_runner.pr_metadata import pr_metadata_prompt_instructions
from agents_runner.ui.constants import PIXELARCH_EMERALD_IMAGE
from agents_runner.ui.main_window_tasks_interactive_command import (
    build_agent_command_parts,
)


class InteractivePrepWorker(QObject):
    stage = Signal(str, str, str)  # task_id, status, message
    log = Signal(str, str)  # task_id, line
    succeeded = Signal(str, dict)  # task_id, payload
    failed = Signal(str, str)  # task_id, error

    def __init__(
        self,
        *,
        task_id: str,
        env_id: str,
        workspace_type: str,
        gh_repo: str,
        host_workdir: str,
        desired_base: str,
        gh_use_host_cli: bool,
        gh_context_enabled: bool,
        data_dir: str,
        image: str,
        command: str,
        agent_cli: str,
        agent_cli_args: list[str],
        prompt_for_agent: str,
        is_help_launch: bool,
        prep_id: str = "",
    ) -> None:
        super().__init__()
        self._task_id = str(task_id or "").strip()
        self._env_id = str(env_id or "").strip()
        self._workspace_type = str(workspace_type or "").strip()
        self._gh_repo = str(gh_repo or "").strip()
        self._host_workdir = str(host_workdir or "").strip()
        self._desired_base = str(desired_base or "").strip()
        self._gh_use_host_cli = bool(gh_use_host_cli)
        self._gh_context_enabled = bool(gh_context_enabled)
        self._data_dir = str(data_dir or "").strip()
        self._image = str(image or PIXELARCH_EMERALD_IMAGE).strip()
        self._command = str(command or "").strip()
        self._agent_cli = str(agent_cli or "").strip()
        self._agent_cli_args = list(agent_cli_args or [])
        self._prompt_for_agent = str(prompt_for_agent or "")
        self._is_help_launch = bool(is_help_launch)
        self._prep_id = str(prep_id or "").strip()
        self._stop_requested = False

    @Slot()
    def request_stop(self) -> None:
        self._stop_requested = True

    def _check_stop(self) -> None:
        if self._stop_requested:
            raise RuntimeError("Interactive preparation was cancelled.")

    def _emit_stage(self, status: str, message: str) -> None:
        self.stage.emit(self._task_id, status, message)
        self.log.emit(self._task_id, format_log("ui", "prep", "INFO", message))

    def _diag(self, level: str, message: str) -> None:
        level_text = str(level or "INFO").strip().upper() or "INFO"
        if level_text not in {"WARN", "ERROR"}:
            return
        prep_prefix = f"[prep:{self._prep_id}] " if self._prep_id else ""
        self.log.emit(
            self._task_id,
            format_log("ui", "prepdiag", level_text, f"{prep_prefix}{message}"),
        )

    def _pull_image(self) -> None:
        pull_started_s = time.monotonic()
        pull_parts = [
            "docker",
            "pull",
            *docker_platform_args_for_pixelarch(),
            self._image,
        ]
        self._diag("INFO", f"docker pull start image={self._image}")
        self.log.emit(
            self._task_id,
            format_log(
                "docker",
                "cmd",
                "INFO",
                " ".join(shlex.quote(part) for part in pull_parts),
            ),
        )
        completed = subprocess.run(
            pull_parts,
            check=False,
            capture_output=True,
            text=True,
        )
        lines = (f"{completed.stdout or ''}\n{completed.stderr or ''}").splitlines()
        for raw in lines[-80:]:
            line = str(raw or "").strip()
            if line:
                self.log.emit(self._task_id, format_log("docker", "pull", "INFO", line))
        if completed.returncode != 0:
            detail = (
                (completed.stderr or "").strip()
                or (completed.stdout or "").strip()
                or f"docker pull failed with exit code {completed.returncode}"
            )
            raise RuntimeError(detail)
        pull_elapsed_ms = (time.monotonic() - pull_started_s) * 1000.0
        self._diag("INFO", f"docker pull done elapsed_ms={pull_elapsed_ms:.0f}")

    @Slot()
    def run(self) -> None:
        try:
            run_started_s = time.monotonic()
            self._diag("INFO", "worker started")
            self._check_stop()
            gh_repo_root = ""
            gh_base_branch = self._desired_base
            gh_branch = ""
            pr_host_path = ""
            pr_metadata_mount = ""
            prompt_for_agent = self._prompt_for_agent

            if self._workspace_type == WORKSPACE_CLONED and self._gh_repo:
                self._emit_stage("starting", "Preparing task workspace")
                cleanup_started_s = time.monotonic()
                self._diag("INFO", "phase=workspace_prepare begin")
                if os.path.exists(self._host_workdir):
                    cleanup_success = cleanup_task_workspace(
                        env_id=self._env_id,
                        task_id=self._task_id,
                        data_dir=self._data_dir,
                        on_log=lambda line: self.log.emit(
                            self._task_id, str(line or "")
                        ),
                    )
                    if not cleanup_success:
                        raise RuntimeError(
                            "Unable to prepare a fresh cloned workspace for this task."
                        )
                cleanup_elapsed_ms = (time.monotonic() - cleanup_started_s) * 1000.0
                self._diag(
                    "INFO",
                    f"phase=workspace_prepare done elapsed_ms={cleanup_elapsed_ms:.0f}",
                )

                self._check_stop()
                self._emit_stage("cloning", "Syncing repository and preparing branch")
                clone_started_s = time.monotonic()
                self._diag("INFO", "phase=repo_clone_or_sync begin")
                try:
                    gh_result = prepare_github_repo_for_task(
                        self._gh_repo,
                        self._host_workdir,
                        task_id=self._task_id,
                        base_branch=self._desired_base or None,
                        prefer_gh=self._gh_use_host_cli,
                        recreate_if_needed=False,
                        on_log=lambda line: self.log.emit(
                            self._task_id, str(line or "")
                        ),
                    )
                except GhManagementError as exc:
                    raise RuntimeError(str(exc)) from exc
                clone_elapsed_ms = (time.monotonic() - clone_started_s) * 1000.0
                self._diag(
                    "INFO",
                    f"phase=repo_clone_or_sync done elapsed_ms={clone_elapsed_ms:.0f}",
                )

                gh_repo_root = str(gh_result.get("repo_root") or "").strip()
                gh_base_branch = str(gh_result.get("base_branch") or "").strip()
                gh_branch = str(gh_result.get("branch") or "").strip()
                if not gh_repo_root or not gh_branch:
                    raise RuntimeError(
                        "Could not prepare a task branch for this cloned repository."
                    )

                if self._gh_context_enabled:
                    self._check_stop()
                    self._emit_stage("starting", "Preparing PR metadata file")
                    metadata_started_s = time.monotonic()
                    self._diag("INFO", "phase=pr_metadata_prepare begin")
                    pr_host_path = pr_metadata_host_path(self._data_dir, self._task_id)
                    pr_container_path = pr_metadata_container_path(self._task_id)
                    try:
                        ensure_pr_metadata_file(pr_host_path, task_id=self._task_id)
                    except Exception as exc:
                        raise RuntimeError(
                            f"Could not create PR metadata file: {exc}"
                        ) from exc
                    pr_metadata_mount = f"{pr_host_path}:{pr_container_path}:rw"
                    prompt_for_agent = (
                        f"{prompt_for_agent}"
                        f"{pr_metadata_prompt_instructions(pr_container_path)}"
                    )
                    metadata_elapsed_ms = (
                        time.monotonic() - metadata_started_s
                    ) * 1000.0
                    self._diag(
                        "INFO",
                        f"phase=pr_metadata_prepare done elapsed_ms={metadata_elapsed_ms:.0f}",
                    )

            self._check_stop()
            self._emit_stage("pulling", f"Ensuring image is available: {self._image}")
            self._diag("INFO", "phase=image_ready begin")
            self._pull_image()
            self._diag("INFO", "phase=image_ready done")

            self._check_stop()
            cmd_started_s = time.monotonic()
            self._diag("INFO", "phase=command_build begin")
            cmd_parts = build_agent_command_parts(
                command=self._command,
                agent_cli=self._agent_cli,
                agent_cli_args=self._agent_cli_args,
                prompt=prompt_for_agent,
                is_help_launch=self._is_help_launch,
            )
            cmd_elapsed_ms = (time.monotonic() - cmd_started_s) * 1000.0
            self._diag(
                "INFO", f"phase=command_build done elapsed_ms={cmd_elapsed_ms:.0f}"
            )

            self._emit_stage("starting", "Launching interactive terminal")
            total_elapsed_ms = (time.monotonic() - run_started_s) * 1000.0
            self._diag("INFO", f"worker succeeded elapsed_ms={total_elapsed_ms:.0f}")
            self.succeeded.emit(
                self._task_id,
                {
                    "gh_repo_root": gh_repo_root,
                    "gh_base_branch": gh_base_branch or self._desired_base,
                    "gh_branch": gh_branch,
                    "gh_pr_metadata_path": pr_host_path,
                    "pr_metadata_mount": pr_metadata_mount,
                    "cmd_parts": cmd_parts,
                },
            )
        except Exception as exc:
            self._diag("ERROR", f"worker failed error={exc}")
            self.failed.emit(self._task_id, str(exc))
