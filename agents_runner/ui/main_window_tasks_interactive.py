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
from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import save_environment
from agents_runner.gh_management import is_gh_available
from agents_runner.prompt_sanitizer import sanitize_prompt
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

        workspace_type = (
            env.workspace_type
            if env
            else "none"
        )
        host_workdir, ready, message = self._new_task_workspace(env, task_id=task_id)
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return

        if workspace_type != WORKSPACE_CLONED and not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        if env and os.path.isdir(host_workdir):
            try:
                from agents_runner.midoriai_template import scan_midoriai_agents_template

                detection = scan_midoriai_agents_template(host_workdir)
                env.midoriai_template_likelihood = detection.midoriai_template_likelihood
                env.midoriai_template_detected = detection.midoriai_template_detected
                env.midoriai_template_detected_path = detection.midoriai_template_detected_path
                save_environment(env)
                self._environments[env.env_id] = env
            except Exception:
                pass

        desired_base = str(base_branch or "").strip()

        # Save the selected branch for cloned environments
        if (
            env
            and env.workspace_type == WORKSPACE_CLONED
            and desired_base
        ):
            env.gh_last_base_branch = desired_base
            save_environment(env)
            # Update in-memory copy to persist across tab changes and reloads
            self._environments[env.env_id] = env

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
            interactive_key = self._interactive_command_key(agent_cli)
            raw_command = str(self._settings_data.get(interactive_key) or "").strip()
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

        try:
            cmd_parts = build_agent_command_parts(
                command=command,
                agent_cli=agent_cli,
                agent_cli_args=agent_cli_args,
                prompt=prompt,
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

        container_name = f"codex-gui-it-{task_id}"
        container_agent_dir = container_config_dir(agent_cli)
        config_extra_mounts = additional_config_mounts(agent_cli, host_codex)
        container_workdir = "/home/midori-ai/workspace"

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=host_workdir,
            host_codex_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="starting",
            container_id=container_name,
            gh_use_host_cli=(
                bool(getattr(env, "gh_use_host_cli", True)) if env else True
            ),
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

        task.gh_use_host_cli = bool(task.gh_use_host_cli and is_gh_available())

        # Extract gh_repo from environment if GitHub management is enabled
        gh_repo: str = ""
        if workspace_type == WORKSPACE_CLONED and env:
            gh_repo = str(env.workspace_target or "").strip()

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
            gh_repo=gh_repo,
            gh_prefer_gh_cli=bool(task.gh_use_host_cli),
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
            self.interactive_finished.emit(task_id, int(exit_code))

        threading.Thread(target=_worker, daemon=True).start()
