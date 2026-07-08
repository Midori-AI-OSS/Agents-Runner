from __future__ import annotations

import os
import shlex
import subprocess
import time

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from agents_runner.agent_install import probe_agent_executable_in_image
from agents_runner.agent_install import resolve_agent_install_plan
from agents_runner.docker.agent_worker_prompt import PromptAssembler
from agents_runner.docker.process import has_image
from agents_runner.docker.process import has_platform_image
from agents_runner.docker.cache_resolver import resolve_runtime_cache
from agents_runner.docker.phase_image_builder import PREFLIGHTS_DIR
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.docker_platform import docker_platform_for_pixelarch
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.environments.git_operations import get_git_info
from agents_runner.gh_management import GhManagementError
from agents_runner.gh_management import prepare_github_repo_for_task
from agents_runner.log_format import format_log
from agents_runner.midoriai_template import MidoriaiTemplateDetection
from agents_runner.midoriai_template import scan_midoriai_agents_template
from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.prompts import load_prompt
from agents_runner.prompts.sections import insert_prompt_sections_before_user_prompt
from agents_runner.pr_metadata import ensure_pr_metadata_file
from agents_runner.pr_metadata import github_context_prompt_instructions
from agents_runner.pr_metadata import pr_metadata_container_path
from agents_runner.pr_metadata import pr_metadata_host_path
from agents_runner.pr_metadata import pr_metadata_prompt_instructions
from agents_runner.setup_agents import missing_setup_agents_instruction
from agents_runner.setup_agents import prepare_setup_agents_phase
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
        workspace_target: str,
        gh_repo: str,
        host_workdir: str,
        desired_base: str,
        gh_use_host_cli: bool,
        gh_context_enabled: bool,
        gh_pr_unavailable_reason: str,
        gh_pr_unavailable_status: str,
        data_dir: str,
        image: str,
        command: str,
        agent_cli: str,
        agent_cli_args: list[str],
        prompt_for_agent: str,
        apply_full_prompting: bool,
        has_typed_prompt: bool,
        desktop_enabled: bool,
        settings_preflight_script: str | None,
        extra_preflight_script: str,
        launch_mode: str,
        container_caching_enabled: bool,
        cache_system_preflight_enabled: bool,
        cache_settings_preflight_enabled: bool,
        cache_desktop_build: bool,
        setup_agents_missing_prompt_enabled: bool,
        pull_before_run: bool,
        branch_work_mode: str,
        task_branch_naming_style: str,
        task_branch_custom_template: str,
        prep_id: str = "",
    ) -> None:
        super().__init__()
        self._task_id = str(task_id or "").strip()
        self._env_id = str(env_id or "").strip()
        self._workspace_type = str(workspace_type or "").strip()
        self._workspace_target = str(workspace_target or "").strip()
        self._gh_repo = str(gh_repo or "").strip()
        self._host_workdir = str(host_workdir or "").strip()
        self._desired_base = str(desired_base or "").strip()
        self._gh_use_host_cli = bool(gh_use_host_cli)
        self._gh_context_enabled = bool(gh_context_enabled)
        self._gh_pr_unavailable_reason = str(gh_pr_unavailable_reason or "").strip()
        self._gh_pr_unavailable_status = str(gh_pr_unavailable_status or "").strip()
        self._data_dir = str(data_dir or "").strip()
        self._image = str(image or PIXELARCH_EMERALD_IMAGE).strip()
        self._command = str(command or "").strip()
        self._agent_cli = str(agent_cli or "").strip()
        self._agent_cli_args = list(agent_cli_args or [])
        self._prompt_for_agent = str(prompt_for_agent or "")
        self._apply_full_prompting = bool(apply_full_prompting)
        self._has_typed_prompt = bool(has_typed_prompt)
        self._desktop_enabled = bool(desktop_enabled)
        self._settings_preflight_script = str(settings_preflight_script or "")
        self._extra_preflight_script = str(extra_preflight_script or "")
        self._launch_mode = str(launch_mode or "interactive_agent").strip().lower()
        self._container_caching_enabled = bool(container_caching_enabled)
        self._cache_system_preflight_enabled = bool(cache_system_preflight_enabled)
        self._cache_settings_preflight_enabled = bool(cache_settings_preflight_enabled)
        self._cache_desktop_build = bool(cache_desktop_build)
        self._setup_agents_missing_prompt_enabled = bool(setup_agents_missing_prompt_enabled)
        self._pull_before_run = bool(pull_before_run)
        self._branch_work_mode = str(branch_work_mode or "").strip() or "task_branch"
        self._task_branch_naming_style = str(task_branch_naming_style or "").strip() or "standard"
        self._task_branch_custom_template = str(task_branch_custom_template or "").strip() or "{task_id}"
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

    def _ensure_local_image_available(self) -> None:
        platform_value = docker_platform_for_pixelarch()
        image_present = has_platform_image(self._image, platform_value) if platform_value else has_image(self._image)
        if image_present:
            return

        platform_suffix = f" ({platform_value})" if platform_value else ""
        raise RuntimeError(
            f"Base image {self._image}{platform_suffix} is not available locally "
            "and pull-before-run is disabled for this environment."
        )

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

    def _resolve_runtime_image_for_launch(self, *, cmd_parts: list[str]) -> dict[str, object]:
        agent_probe_available: bool | None = None
        if cmd_parts:
            agent_probe_available = probe_agent_executable_in_image(
                image=self._image,
                agent_cli=str(cmd_parts[0]),
                platform_args=docker_platform_args_for_pixelarch(),
                task_token=self._task_id or "task",
            )
            self.log.emit(
                self._task_id,
                format_log(
                    "install",
                    "probe",
                    "INFO",
                    (
                        f"image probe ({self._image}) agent={str(cmd_parts[0])}: "
                        f"{'available' if agent_probe_available else 'missing'}"
                    ),
                ),
            )

        install_plan = None
        if cmd_parts and agent_probe_available is not True:
            install_plan = resolve_agent_install_plan(
                agent_cli=str(cmd_parts[0]),
                include_internal=False,
            )
        install_preflight_script = str(install_plan.script_content or "").strip() if install_plan else ""
        install_phase_name = str(install_plan.phase_name or "").strip() if install_plan else ""

        cache_install_enabled = bool(self._container_caching_enabled)
        cache_system_enabled = bool(self._container_caching_enabled and self._cache_system_preflight_enabled)
        cache_settings_enabled = bool(self._container_caching_enabled and self._cache_settings_preflight_enabled)
        desktop_cache_enabled = bool(self._cache_desktop_build and self._desktop_enabled)
        if agent_probe_available is True and cache_system_enabled:
            cache_system_enabled = False
            self.log.emit(
                self._task_id,
                format_log(
                    "phase",
                    "cache",
                    "INFO",
                    "system preflight cache skipped: agent executable is already available in pulled image",
                ),
            )

        def on_phase_log(line: str) -> None:
            self.log.emit(self._task_id, str(line or ""))

        result = resolve_runtime_cache(
            base_image=self._image,
            cache_install_enabled=cache_install_enabled,
            install_preflight_script=install_preflight_script,
            install_phase_name=install_phase_name,
            cache_system_enabled=cache_system_enabled,
            cache_settings_enabled=cache_settings_enabled,
            desktop_cache_enabled=desktop_cache_enabled,
            extra_preflight_script=str(self._extra_preflight_script or ""),
            settings_preflight_script=self._settings_preflight_script,
            preflights_host_dir=PREFLIGHTS_DIR.resolve(),
            on_log=on_phase_log,
            check_stop=self._check_stop,
        )

        return {
            "runtime_image": result.runtime_image,
            "install_preflight_cached": result.install_preflight_cached,
            "system_preflight_cached": result.system_preflight_cached,
            "desktop_preflight_cached": result.desktop_preflight_cached,
            "settings_preflight_cached": result.settings_preflight_cached,
            "resolved_extra_preflight_script": result.desktop_preflight_script,
            "install_preflight_script": install_preflight_script,
            "install_phase_name": install_phase_name,
            "agent_probe_available": agent_probe_available,
            "skip_system_preflight": agent_probe_available is True,
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
        if self._gh_pr_unavailable_reason and self._apply_full_prompting:
            pr_instruction = ""
        elif self._gh_pr_unavailable_reason:
            pr_instruction = load_prompt(
                "github_recommendation_only",
                REASON=self._gh_pr_unavailable_reason,
            )
        else:
            pr_instruction = pr_metadata_prompt_instructions(pr_container_path)
        return insert_prompt_sections_before_user_prompt(
            prompt_for_agent,
            [
                (
                    f"{github_context_prompt_instructions(repo_url=repo_url, repo_owner=repo_owner, repo_name=repo_name, base_branch=base_branch, task_branch=task_branch, head_commit=head_commit)}"
                    f"{pr_instruction}"
                )
            ],
        )

    def _apply_interactive_template_and_standby_prompt(self, prompt: str) -> str:
        prompt_for_agent = str(prompt or "")

        template_detection: MidoriaiTemplateDetection
        try:
            template_detection = scan_midoriai_agents_template(self._host_workdir)
        except Exception:
            template_detection = MidoriaiTemplateDetection(
                midoriai_template_likelihood=0.0,
                midoriai_template_detected=False,
                midoriai_template_detected_path=None,
            )

        assembler = PromptAssembler(
            prompt_for_agent,
            self._env_id or None,
            lambda line: self.log.emit(self._task_id, str(line or "")),
            state_path=os.path.join(self._data_dir, "state.toml"),
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
            prompt_for_agent = insert_prompt_sections_before_user_prompt(
                prompt_for_agent,
                [sanitize_prompt(standby_prompt)],
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
            setup_agents_script = ""

            if self._workspace_type == WORKSPACE_CLONED and self._gh_repo:
                self._emit_stage("starting", "Preparing task workspace")
                cleanup_started_s = time.monotonic()
                self._diag("INFO", "phase=workspace_prepare begin")
                if os.path.exists(self._host_workdir):
                    cleanup_success = cleanup_task_workspace(
                        env_id=self._env_id,
                        task_id=self._task_id,
                        data_dir=self._data_dir,
                        on_log=lambda line: self.log.emit(self._task_id, str(line or "")),
                    )
                    if not cleanup_success:
                        raise RuntimeError("Unable to prepare a fresh cloned workspace for this task.")
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
                        branch_work_mode=self._branch_work_mode,
                        task_branch_naming_style=self._task_branch_naming_style,
                        task_branch_custom_template=self._task_branch_custom_template,
                        prefer_gh=self._gh_use_host_cli,
                        recreate_if_needed=False,
                        on_log=lambda line: self.log.emit(self._task_id, str(line or "")),
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
                    raise RuntimeError("Could not prepare this cloned repository for the task.")

                if self._gh_context_enabled:
                    self._check_stop()
                    self._emit_stage("starting", "Preparing GitHub context")
                    metadata_started_s = time.monotonic()
                    self._diag("INFO", "phase=pr_metadata_prepare begin")
                    if not self._gh_pr_unavailable_reason:
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
                    metadata_elapsed_ms = (time.monotonic() - metadata_started_s) * 1000.0
                    self._diag(
                        "INFO",
                        f"phase=pr_metadata_prepare done elapsed_ms={metadata_elapsed_ms:.0f}",
                    )

            setup_agents_prompt_instruction: str | None = None
            try:
                setup_agents_result = prepare_setup_agents_phase(
                    host_workdir=self._host_workdir,
                    environment_id=self._env_id,
                    workspace_type=self._workspace_type,
                    workspace_target=self._workspace_target,
                    gh_repo=self._gh_repo or None,
                    launch_mode=self._launch_mode,
                    on_log=lambda line: self.log.emit(self._task_id, str(line or "")),
                )
            except Exception as exc:
                self.log.emit(
                    self._task_id,
                    format_log(
                        "setup",
                        "agents",
                        "WARN",
                        f"setup-agents preparation failed; continuing without setup phase: {exc}",
                    ),
                )
                setup_agents_script = ""
                if self._setup_agents_missing_prompt_enabled:
                    setup_agents_prompt_instruction = missing_setup_agents_instruction(launch_mode=self._launch_mode)
            else:
                setup_agents_script = str(setup_agents_result.setup_script or "")
                setup_agents_prompt_instruction = setup_agents_result.prompt_instruction
                if not self._setup_agents_missing_prompt_enabled and not setup_agents_script.strip():
                    setup_agents_prompt_instruction = None
                    self.log.emit(
                        self._task_id,
                        format_log(
                            "setup",
                            "agents",
                            "INFO",
                            "setup-agents prompt guidance suppressed by environment setting",
                        ),
                    )

            if setup_agents_prompt_instruction and self._has_typed_prompt:
                prompt_for_agent = insert_prompt_sections_before_user_prompt(
                    prompt_for_agent,
                    [sanitize_prompt(setup_agents_prompt_instruction)],
                )

            if self._workspace_type != WORKSPACE_CLONED and self._gh_context_enabled and self._apply_full_prompting:
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
                prompt_for_agent = self._apply_interactive_template_and_standby_prompt(prompt_for_agent)

            self._check_stop()
            image_status = (
                f"Ensuring image is available: {self._image}"
                if self._pull_before_run
                else f"Checking local image availability: {self._image}"
            )
            self._emit_stage("pulling", image_status)
            self._diag("INFO", "phase=image_ready begin")
            if self._pull_before_run:
                self._pull_image()
            else:
                self._ensure_local_image_available()
            self._diag("INFO", "phase=image_ready done")

            self._check_stop()
            cmd_started_s = time.monotonic()
            self._diag("INFO", "phase=command_build begin")
            cmd_parts = build_agent_command_parts(
                command=self._command,
                agent_cli=self._agent_cli,
                agent_cli_args=self._agent_cli_args,
                prompt=prompt_for_agent,
            )
            cmd_elapsed_ms = (time.monotonic() - cmd_started_s) * 1000.0
            self._diag("INFO", f"phase=command_build done elapsed_ms={cmd_elapsed_ms:.0f}")

            self._check_stop()
            self._emit_stage("starting", "Preparing runtime image cache")
            cache_resolve_started_s = time.monotonic()
            self._diag("INFO", "phase=interactive_cache_resolve begin")
            cache_resolution = self._resolve_runtime_image_for_launch(cmd_parts=cmd_parts)
            cache_resolve_elapsed_ms = (time.monotonic() - cache_resolve_started_s) * 1000.0
            self._diag(
                "INFO",
                f"phase=interactive_cache_resolve done elapsed_ms={cache_resolve_elapsed_ms:.0f}",
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
                    "gh_pr_unavailable_reason": self._gh_pr_unavailable_reason,
                    "gh_pr_unavailable_status": self._gh_pr_unavailable_status,
                    "pr_metadata_mount": pr_metadata_mount,
                    "cmd_parts": cmd_parts,
                    "runtime_image": cache_resolution.get("runtime_image"),
                    "install_preflight_cached": cache_resolution.get("install_preflight_cached", False),
                    "system_preflight_cached": cache_resolution.get("system_preflight_cached", False),
                    "desktop_preflight_cached": cache_resolution.get("desktop_preflight_cached", False),
                    "settings_preflight_cached": cache_resolution.get("settings_preflight_cached", False),
                    "resolved_extra_preflight_script": cache_resolution.get("resolved_extra_preflight_script", ""),
                    "install_preflight_script": cache_resolution.get("install_preflight_script", ""),
                    "install_phase_name": cache_resolution.get("install_phase_name", ""),
                    "agent_probe_available": cache_resolution.get("agent_probe_available"),
                    "skip_system_preflight": bool(cache_resolution.get("skip_system_preflight", False)),
                    "setup_agents_script": setup_agents_script,
                },
            )
        except Exception as exc:
            self._diag("ERROR", f"worker failed error={exc}")
            self.failed.emit(self._task_id, str(exc))
