from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from agents_runner.docker.agent_worker_prompt import PromptAssembler
from agents_runner.docker.image_builder import ensure_desktop_image
from agents_runner.docker.phase_image_builder import PREFLIGHTS_DIR
from agents_runner.docker.phase_image_builder import ensure_phase_image
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.environments.git_operations import get_git_info
from agents_runner.gh_management import GhManagementError
from agents_runner.gh_management import prepare_github_repo_for_task
from agents_runner.log_format import format_log
from agents_runner.midoriai_template import MidoriAITemplateDetection
from agents_runner.midoriai_template import scan_midoriai_agents_template
from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.prompts import load_prompt
from agents_runner.pr_metadata import ensure_pr_metadata_file
from agents_runner.pr_metadata import github_context_prompt_instructions
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
        apply_full_prompting: bool,
        desktop_enabled: bool,
        settings_preflight_script: str | None,
        extra_preflight_script: str,
        container_caching_enabled: bool,
        cache_system_preflight_enabled: bool,
        cache_settings_preflight_enabled: bool,
        cache_desktop_build: bool,
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
        self._apply_full_prompting = bool(apply_full_prompting)
        self._desktop_enabled = bool(desktop_enabled)
        self._settings_preflight_script = str(settings_preflight_script or "")
        self._extra_preflight_script = str(extra_preflight_script or "")
        self._container_caching_enabled = bool(container_caching_enabled)
        self._cache_system_preflight_enabled = bool(cache_system_preflight_enabled)
        self._cache_settings_preflight_enabled = bool(cache_settings_preflight_enabled)
        self._cache_desktop_build = bool(cache_desktop_build)
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

    def _prepare_pr_metadata_file(self) -> tuple[str, str, str]:
        pr_host_path = pr_metadata_host_path(self._data_dir, self._task_id)
        pr_container_path = pr_metadata_container_path(self._task_id)
        try:
            ensure_pr_metadata_file(pr_host_path, task_id=self._task_id)
        except Exception as exc:
            raise RuntimeError(f"Could not create PR metadata file: {exc}") from exc
        return (
            pr_host_path,
            pr_container_path,
            f"{pr_host_path}:{pr_container_path}:rw",
        )

    def _resolve_runtime_image_for_launch(self) -> dict[str, object]:
        runtime_image = self._image
        desktop_preflight_script = str(self._extra_preflight_script or "")
        preflights_host_dir = PREFLIGHTS_DIR.resolve()

        system_preflight_cached = False
        desktop_preflight_cached = False
        settings_preflight_cached = False
        environment_preflight_cached = False

        cache_system_enabled = bool(
            self._container_caching_enabled and self._cache_system_preflight_enabled
        )
        cache_settings_enabled = bool(
            self._container_caching_enabled and self._cache_settings_preflight_enabled
        )
        desktop_cache_enabled = bool(
            self._cache_desktop_build and self._desktop_enabled
        )

        def on_phase_log(line: str) -> None:
            self.log.emit(self._task_id, str(line or ""))

        system_preflight_script = ""
        system_preflight_path = preflights_host_dir / "pixelarch_yay.sh"
        if system_preflight_path.is_file():
            try:
                system_preflight_script = system_preflight_path.read_text(
                    encoding="utf-8"
                )
            except Exception:
                system_preflight_script = ""

        if cache_system_enabled and system_preflight_script.strip():
            self._check_stop()
            next_image = ensure_phase_image(
                base_image=runtime_image,
                phase_name="system",
                script_content=system_preflight_script,
                preflights_dir=preflights_host_dir,
                on_log=on_phase_log,
            )
            system_preflight_cached = next_image != runtime_image
            runtime_image = next_image
        elif cache_system_enabled:
            on_phase_log(
                format_log(
                    "phase",
                    "cache",
                    "WARN",
                    "system caching enabled but system script is unavailable",
                )
            )

        if desktop_cache_enabled:
            self._check_stop()
            desktop_base_image = runtime_image
            next_image = ensure_desktop_image(desktop_base_image, on_log=on_phase_log)
            desktop_preflight_cached = next_image != desktop_base_image
            runtime_image = next_image
            if desktop_preflight_cached:
                desktop_run_path = Path(preflights_host_dir) / "desktop_run.sh"
                try:
                    desktop_preflight_script = desktop_run_path.read_text(
                        encoding="utf-8"
                    )
                except Exception:
                    desktop_preflight_script = ""
                if not desktop_preflight_script.strip():
                    on_phase_log(
                        format_log(
                            "desktop",
                            "cache",
                            "WARN",
                            f"desktop cache active but runtime script is missing: {desktop_run_path}",
                        )
                    )
                    desktop_preflight_cached = False
                    runtime_image = desktop_base_image

        if cache_settings_enabled and self._settings_preflight_script.strip():
            self._check_stop()
            next_image = ensure_phase_image(
                base_image=runtime_image,
                phase_name="settings",
                script_content=self._settings_preflight_script,
                preflights_dir=preflights_host_dir,
                on_log=on_phase_log,
            )
            settings_preflight_cached = next_image != runtime_image
            runtime_image = next_image
        elif cache_settings_enabled:
            on_phase_log(
                format_log(
                    "phase",
                    "cache",
                    "WARN",
                    "settings caching enabled but settings script is empty",
                )
            )

        return {
            "runtime_image": runtime_image,
            "system_preflight_cached": system_preflight_cached,
            "desktop_preflight_cached": desktop_preflight_cached,
            "settings_preflight_cached": settings_preflight_cached,
            "environment_preflight_cached": environment_preflight_cached,
            "resolved_extra_preflight_script": desktop_preflight_script,
        }

    def _append_full_prompt_github_context(
        self,
        *,
        prompt_for_agent: str,
        pr_container_path: str,
        repo_url: str,
        repo_owner: str,
        repo_name: str,
        base_branch: str,
        task_branch: str,
        head_commit: str,
    ) -> str:
        return (
            f"{prompt_for_agent}"
            f"{github_context_prompt_instructions(repo_url=repo_url, repo_owner=repo_owner, repo_name=repo_name, base_branch=base_branch, task_branch=task_branch, head_commit=head_commit)}"
            f"{pr_metadata_prompt_instructions(pr_container_path)}"
        )

    def _apply_interactive_template_and_standby_prompt(self, prompt: str) -> str:
        prompt_for_agent = str(prompt or "")

        template_detection: MidoriAITemplateDetection
        try:
            template_detection = scan_midoriai_agents_template(self._host_workdir)
        except Exception:
            template_detection = MidoriAITemplateDetection(
                midoriai_template_likelihood=0.0,
                midoriai_template_detected=False,
                midoriai_template_detected_path=None,
            )

        assembler = PromptAssembler(
            prompt_for_agent,
            self._env_id or None,
            lambda line: self.log.emit(self._task_id, str(line or "")),
        )
        prompt_for_agent = assembler.assemble_prompt(
            self._agent_cli,
            template_detection,
            self._desktop_enabled,
            ":1",
        )

        try:
            standby_prompt = load_prompt("interactive_standby").strip()
        except Exception as exc:
            self.log.emit(
                self._task_id,
                format_log(
                    "ui",
                    "prep",
                    "WARN",
                    f"failed to load interactive standby prompt: {exc}",
                ),
            )
            standby_prompt = ""

        if standby_prompt:
            prompt_for_agent = sanitize_prompt(
                f"{prompt_for_agent.rstrip()}\n\n{standby_prompt}"
            )

        return prompt_for_agent

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
            pr_container_path = ""
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
                    (
                        pr_host_path,
                        pr_container_path,
                        pr_metadata_mount,
                    ) = self._prepare_pr_metadata_file()
                    if self._apply_full_prompting:
                        git_info = get_git_info(gh_repo_root)
                        if git_info:
                            prompt_for_agent = self._append_full_prompt_github_context(
                                prompt_for_agent=prompt_for_agent,
                                pr_container_path=pr_container_path,
                                repo_url=git_info.repo_url,
                                repo_owner=git_info.repo_owner or "",
                                repo_name=git_info.repo_name or "",
                                base_branch=git_info.branch,
                                task_branch=gh_branch,
                                head_commit=git_info.commit_sha,
                            )
                        else:
                            prompt_for_agent = self._append_full_prompt_github_context(
                                prompt_for_agent=prompt_for_agent,
                                pr_container_path=pr_container_path,
                                repo_url=self._gh_repo,
                                repo_owner="",
                                repo_name="",
                                base_branch=gh_base_branch or self._desired_base,
                                task_branch=gh_branch,
                                head_commit="(unknown)",
                            )
                    elif self._is_help_launch:
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

            if (
                self._workspace_type != WORKSPACE_CLONED
                and self._gh_context_enabled
                and self._apply_full_prompting
            ):
                git_info = get_git_info(self._host_workdir)
                if git_info:
                    self._check_stop()
                    self._emit_stage("starting", "Preparing PR metadata file")
                    (
                        pr_host_path,
                        pr_container_path,
                        pr_metadata_mount,
                    ) = self._prepare_pr_metadata_file()
                    prompt_for_agent = self._append_full_prompt_github_context(
                        prompt_for_agent=prompt_for_agent,
                        pr_container_path=pr_container_path,
                        repo_url=git_info.repo_url,
                        repo_owner=git_info.repo_owner or "",
                        repo_name=git_info.repo_name or "",
                        base_branch=git_info.branch,
                        task_branch=git_info.branch,
                        head_commit=git_info.commit_sha,
                    )

            if self._apply_full_prompting:
                prompt_for_agent = self._apply_interactive_template_and_standby_prompt(
                    prompt_for_agent
                )

            self._check_stop()
            self._emit_stage("pulling", f"Ensuring image is available: {self._image}")
            self._diag("INFO", "phase=image_ready begin")
            self._pull_image()
            self._diag("INFO", "phase=image_ready done")

            self._check_stop()
            self._emit_stage("starting", "Preparing runtime image cache")
            cache_resolve_started_s = time.monotonic()
            self._diag("INFO", "phase=interactive_cache_resolve begin")
            cache_resolution = self._resolve_runtime_image_for_launch()
            cache_resolve_elapsed_ms = (
                time.monotonic() - cache_resolve_started_s
            ) * 1000.0
            self._diag(
                "INFO",
                "phase=interactive_cache_resolve done "
                f"elapsed_ms={cache_resolve_elapsed_ms:.0f}",
            )

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
                    "runtime_image": cache_resolution.get("runtime_image"),
                    "system_preflight_cached": cache_resolution.get(
                        "system_preflight_cached", False
                    ),
                    "desktop_preflight_cached": cache_resolution.get(
                        "desktop_preflight_cached", False
                    ),
                    "settings_preflight_cached": cache_resolution.get(
                        "settings_preflight_cached", False
                    ),
                    "environment_preflight_cached": cache_resolution.get(
                        "environment_preflight_cached", False
                    ),
                    "resolved_extra_preflight_script": cache_resolution.get(
                        "resolved_extra_preflight_script", ""
                    ),
                },
            )
        except Exception as exc:
            self._diag("ERROR", f"worker failed error={exc}")
            self.failed.emit(self._task_id, str(exc))
