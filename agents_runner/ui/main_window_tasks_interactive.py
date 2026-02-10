"""Interactive task launching orchestration for MainWindow.

This module handles the high-level orchestration of interactive task launching,
including validation, agent selection, workspace setup, and delegation to
specialized modules for command building and Docker launching.
"""

from __future__ import annotations

import os
import shlex
import shutil
import threading
import time
from uuid import uuid4

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import additional_config_mounts
from agents_runner.agent_cli import container_config_dir
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import save_environment
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.gh_management import GhManagementError
from agents_runner.gh_management import is_gh_available
from agents_runner.gh_management import prepare_github_repo_for_task
from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.pr_metadata import ensure_pr_metadata_file
from agents_runner.pr_metadata import pr_metadata_container_path
from agents_runner.pr_metadata import pr_metadata_host_path
from agents_runner.pr_metadata import pr_metadata_prompt_instructions
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.ui.constants import PIXELARCH_EMERALD_IMAGE
from agents_runner.ui.main_window_tasks_interactive_command import (
    build_agent_command_parts,
)
from agents_runner.ui.main_window_tasks_interactive_docker import (
    launch_docker_terminal_task,
)
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class _MainWindowTasksInteractiveMixin:
    def _start_interactive_task_from_ui(
        self,
        prompt: str,
        command: str,
        host_codex: str,
        env_id: str,
        terminal_id: str,
        base_branch: str,
        extra_preflight_script: str,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(
                self, "Docker not found", "Could not find `docker` in PATH."
            )
            return

        prompt = sanitize_prompt((prompt or "").strip())
        host_codex = os.path.expanduser((host_codex or "").strip())

        options = {opt.terminal_id: opt for opt in detect_terminal_options()}
        opt = options.get(str(terminal_id or "").strip())
        if opt is None:
            QMessageBox.warning(
                self,
                "Terminal not available",
                "The selected terminal could not be found.",
            )
            return

        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(
                self, "Unknown environment", "Pick an environment first."
            )
            return
        env = self._environments.get(env_id)

        task_id = uuid4().hex[:10]
        task_token = f"interactive-{task_id}"

        workspace_type = env.workspace_type if env else "none"
        host_workdir, ready, message = self._new_task_workspace(env, task_id=task_id)
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return

        if workspace_type != WORKSPACE_CLONED and not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        if env and os.path.isdir(host_workdir):
            try:
                from agents_runner.midoriai_template import (
                    scan_midoriai_agents_template,
                )

                # Only update template detection if not already set
                # For cloned workspaces, we scan once and persist the result
                if env.midoriai_template_likelihood == 0.0:
                    detection = scan_midoriai_agents_template(host_workdir)
                    env.midoriai_template_likelihood = (
                        detection.midoriai_template_likelihood
                    )
                    env.midoriai_template_detected = (
                        detection.midoriai_template_detected
                    )
                    env.midoriai_template_detected_path = (
                        detection.midoriai_template_detected_path
                    )
                    save_environment(env)
                    self._environments[env.env_id] = env
            except Exception:
                pass

        desired_base = str(base_branch or "").strip()

        # Save the selected branch for cloned environments
        if env and env.workspace_type == WORKSPACE_CLONED and desired_base:
            env.gh_last_base_branch = desired_base
            save_environment(env)
            # Update in-memory copy to persist across tab changes and reloads
            self._environments[env.env_id] = env

        if (
            env
            and env.agent_selection
            and str(getattr(env.agent_selection, "selection_mode", "") or "")
            .strip()
            .lower()
            == "pinned"
        ):
            pinned_id = str(
                getattr(env.agent_selection, "pinned_agent_id", "") or ""
            ).strip()
            pinned_lower = pinned_id.lower()
            pinned_inst = next(
                (
                    inst
                    for inst in list(getattr(env.agent_selection, "agents", []) or [])
                    if str(getattr(inst, "agent_id", "") or "").strip() == pinned_id
                ),
                None,
            ) or next(
                (
                    inst
                    for inst in list(getattr(env.agent_selection, "agents", []) or [])
                    if str(getattr(inst, "agent_id", "") or "").strip().lower()
                    == pinned_lower
                ),
                None,
            )
            if pinned_inst is None:
                QMessageBox.warning(
                    self,
                    "Pinned agent missing",
                    "This environment is set to Pinned mode, but the pinned agent ID is missing or invalid.",
                )
                return

        # Get effective agent and config dir (environment agent_selection overrides settings)
        agent_instance_id = ""
        if env and env.agent_selection and getattr(env.agent_selection, "agents", None):
            agent_cli, auto_config_dir, agent_instance_id = (
                self._select_agent_instance_for_env(
                    env=env,
                    settings=self._settings_data,
                    advance_round_robin=True,
                )
            )
        else:
            agent_cli, auto_config_dir = self._effective_agent_and_config(
                env=env, advance_round_robin=True
            )
        if not host_codex:
            host_codex = auto_config_dir
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
                return

        # Build command with agent-specific handling
        raw_command = str(command or "").strip()
        if not raw_command:
            raw_command = self._default_interactive_command(agent_cli)
        command = raw_command
        extra_preflight_script = str(extra_preflight_script or "")
        is_help_launch = self._is_agent_help_interactive_launch(
            prompt=prompt, command=command
        )
        if extra_preflight_script.strip() and "clone_repo" in extra_preflight_script:
            is_help_launch = True
        if is_help_launch:
            prompt = "\n".join(
                [
                    f"You are running: `{agent_cli}` right now",
                    "",
                    str(prompt or "").strip(),
                ]
            ).strip()

        prompt_for_agent = str(prompt or "")
        gh_use_host_cli = bool(getattr(env, "gh_use_host_cli", True)) if env else True
        gh_use_host_cli = bool(gh_use_host_cli and is_gh_available())
        gh_repo = (
            str(env.workspace_target or "").strip()
            if workspace_type == WORKSPACE_CLONED and env
            else ""
        )
        gh_repo_root: str | None = None
        gh_base_branch: str | None = None
        gh_branch: str | None = None
        gh_prepare_logs: list[str] = []
        pr_host_path = ""
        pr_metadata_mount = ""

        if workspace_type == WORKSPACE_CLONED and gh_repo:
            if os.path.exists(host_workdir):
                cleanup_success = cleanup_task_workspace(
                    env_id=env_id,
                    task_id=task_id,
                    data_dir=os.path.dirname(self._state_path),
                    on_log=gh_prepare_logs.append,
                )
                if not cleanup_success:
                    QMessageBox.warning(
                        self,
                        "Workspace cleanup failed",
                        "Unable to prepare a fresh cloned workspace for this task.",
                    )
                    return

            try:
                gh_result = prepare_github_repo_for_task(
                    gh_repo,
                    host_workdir,
                    task_id=task_id,
                    base_branch=desired_base or None,
                    prefer_gh=gh_use_host_cli,
                    recreate_if_needed=False,
                    on_log=gh_prepare_logs.append,
                )
            except (GhManagementError, Exception) as exc:
                QMessageBox.warning(self, "GitHub setup failed", str(exc))
                return

            gh_repo_root = str(gh_result.get("repo_root") or "").strip() or None
            gh_base_branch = str(gh_result.get("base_branch") or "").strip() or None
            gh_branch = str(gh_result.get("branch") or "").strip() or None
            if not gh_repo_root or not gh_branch:
                QMessageBox.warning(
                    self,
                    "GitHub setup failed",
                    "Could not prepare a task branch for this cloned repository.",
                )
                return

            if env and env.gh_context_enabled:
                pr_host_path = pr_metadata_host_path(
                    os.path.dirname(self._state_path), task_id
                )
                pr_container_path = pr_metadata_container_path(task_id)
                try:
                    ensure_pr_metadata_file(pr_host_path, task_id=task_id)
                except Exception as exc:
                    QMessageBox.warning(
                        self,
                        "PR metadata setup failed",
                        f"Could not create PR metadata file: {exc}",
                    )
                    return
                pr_metadata_mount = f"{pr_host_path}:{pr_container_path}:rw"
                prompt_for_agent = (
                    f"{prompt_for_agent}"
                    f"{pr_metadata_prompt_instructions(pr_container_path)}"
                )

        try:
            cmd_parts = build_agent_command_parts(
                command=command,
                agent_cli=agent_cli,
                agent_cli_args=agent_cli_args,
                prompt=prompt_for_agent,
                is_help_launch=is_help_launch,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid container command", str(exc))
            return

        image = PIXELARCH_EMERALD_IMAGE

        settings_preflight_script: str | None = None
        if (
            self._settings_data.get("preflight_enabled")
            and str(self._settings_data.get("preflight_script") or "").strip()
        ):
            settings_preflight_script = str(
                self._settings_data.get("preflight_script") or ""
            )

        environment_preflight_script: str | None = None
        if env and env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        container_name = f"agents-runner-tui-it-{task_id}"
        container_agent_dir = container_config_dir(agent_cli)
        config_extra_mounts = additional_config_mounts(agent_cli, host_codex)

        # Add cross-agent config mounts if enabled
        cross_agent_mounts = self._compute_cross_agent_config_mounts(
            env=env,
            primary_agent_cli=agent_cli,
            primary_config_dir=host_codex,
            settings=self._settings_data,
        )
        config_extra_mounts.extend(cross_agent_mounts)
        if pr_metadata_mount:
            config_extra_mounts.append(pr_metadata_mount)

        container_workdir = "/home/midori-ai/workspace"

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=host_workdir,
            host_config_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="starting",
            container_id=container_name,
            gh_use_host_cli=gh_use_host_cli,
            agent_cli=agent_cli,
            agent_instance_id=agent_instance_id,
            agent_cli_args=" ".join(agent_cli_args),
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        if env:
            task.workspace_type = env.workspace_type

        task.gh_repo_root = gh_repo_root or ""
        task.gh_base_branch = gh_base_branch or desired_base
        task.gh_branch = gh_branch or ""
        task.gh_pr_metadata_path = pr_host_path or ""

        for line in gh_prepare_logs:
            self._on_task_log(task_id, str(line or ""))

        # Launch interactive terminal - delegated to Docker launcher module
        launch_docker_terminal_task(
            main_window=self,
            task=task,
            env=env,
            env_id=env_id,
            task_id=task_id,
            task_token=task_token,
            terminal_opt=opt,
            cmd_parts=cmd_parts,
            prompt=prompt,
            command=command,
            agent_cli=agent_cli,
            host_codex=host_codex,
            host_workdir=host_workdir,
            config_extra_mounts=config_extra_mounts,
            image=image,
            container_name=container_name,
            container_agent_dir=container_agent_dir,
            container_workdir=container_workdir,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            extra_preflight_script=extra_preflight_script,
            stain=stain,
            spinner=spinner,
            desired_base=desired_base,
        )

    def _start_interactive_finish_watch(self, task_id: str, finish_path: str) -> None:
        task_id = str(task_id or "").strip()
        finish_path = os.path.abspath(
            os.path.expanduser(str(finish_path or "").strip())
        )
        if not task_id or not finish_path:
            return

        existing = self._interactive_watch.get(task_id)
        if existing is not None:
            _, stop = existing
            stop.set()

        stop_event = threading.Event()
        self._interactive_watch[task_id] = (finish_path, stop_event)

        def _worker() -> None:
            while not stop_event.is_set():
                if os.path.exists(finish_path):
                    break
                time.sleep(0.35)
            if stop_event.is_set():
                return
            exit_code = 0
            for _ in range(6):
                try:
                    with open(finish_path, "r", encoding="utf-8") as f:
                        raw = (f.read() or "").strip().splitlines()[0] if f else ""
                    exit_code = int(raw or "0")
                    break
                except Exception:
                    time.sleep(0.2)

            # Encrypt finish file as artifact before deleting
            try:
                from agents_runner.artifacts import encrypt_artifact

                task_dict = {"id": task_id, "task_id": task_id}
                env_name = getattr(self, "_current_env_name", "unknown")

                artifact_uuid = encrypt_artifact(
                    task_dict=task_dict,
                    env_name=env_name,
                    source_path=finish_path,
                    original_filename=os.path.basename(finish_path),
                )

                if artifact_uuid:
                    logger.rprint(
                        f"[finish] Encrypted finish file as artifact: {artifact_uuid}",
                        mode="normal",
                    )
                else:
                    logger.rprint(
                        "[finish] Failed to encrypt finish file, but continuing",
                        mode="warn",
                    )
            except Exception as exc:
                logger.rprint(
                    f"[finish] Error encrypting finish file: {exc!r}", mode="error"
                )

            # Delete plaintext finish file
            try:
                if os.path.exists(finish_path):
                    os.unlink(finish_path)
                    logger.rprint(
                        f"[finish] Deleted plaintext finish file: {finish_path}",
                        mode="normal",
                    )
            except Exception as exc:
                logger.rprint(
                    f"[finish] Failed to delete finish file: {exc!r}", mode="warn"
                )

            self.interactive_finished.emit(task_id, int(exit_code))

        threading.Thread(target=_worker, daemon=True).start()
