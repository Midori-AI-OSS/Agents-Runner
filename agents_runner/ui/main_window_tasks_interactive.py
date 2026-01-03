from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import threading
import time

from uuid import uuid4

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import normalize_agent
from agents_runner.docker.process import _inspect_state
from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import GH_MANAGEMENT_NONE
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.gh_management import is_gh_available
from agents_runner.github_token import resolve_github_token
from agents_runner.terminal_apps import TerminalOption
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.terminal_apps import launch_in_terminal
from agents_runner.ui.constants import PIXELARCH_EMERALD_IMAGE
from agents_runner.ui.interactive_run import build_interactive_container_command
from agents_runner.ui.interactive_run import build_interactive_terminal_script
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color


class _MainWindowTasksInteractiveMixin:
    def _on_host_state(self, task_id: str, state: object) -> None:
        if isinstance(state, dict):
            self._on_task_state(str(task_id or "").strip(), state)


    def _start_interactive_from_ui(
        self,
        prompt: str,
        command: str,
        host_codex: str,
        env_id: str,
        terminal_id: str,
        base_branch: str,
        launch_preflight_script: str,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return

        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))

        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(self, "Unknown environment", "Pick an environment first.")
            return
        self._settings_data["active_environment_id"] = env_id
        env = self._environments.get(env_id)

        terminal_id = str(terminal_id or "").strip()
        option = self._resolve_terminal_option(terminal_id)
        if option is None:
            QMessageBox.warning(
                self,
                "Terminal not found",
                "Could not detect the selected terminal emulator. Click Refresh and try again.",
            )
            return

        gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE)) if env else GH_MANAGEMENT_NONE
        effective_workdir, ready, message = self._new_task_workspace(env)
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return
        if gh_mode == GH_MANAGEMENT_GITHUB:
            try:
                os.makedirs(effective_workdir, exist_ok=True)
            except Exception:
                pass
        elif not os.path.isdir(effective_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        if not self._can_start_new_agent_for_env(env_id):
            QMessageBox.warning(
                self,
                "At capacity",
                "This environment is already running the maximum number of agents.",
            )
            return

        self._settings_data["interactive_terminal_id"] = terminal_id
        interactive_key = self._interactive_command_key(agent_cli)
        self._settings_data[interactive_key] = str(command or "").strip()

        self._settings_data["host_workdir"] = effective_workdir
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return
        self._settings_data[self._host_config_dir_key(agent_cli)] = host_codex

        env_agent_args: list[str] = []
        if env and str(env.agent_cli_args or "").strip():
            try:
                env_agent_args = shlex.split(str(env.agent_cli_args))
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
                return

        user_cmd = str(command or "").strip()
        try:
            user_parts = shlex.split(user_cmd) if user_cmd else []
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid interactive command", str(exc))
            return

        prompt = str(prompt or "").strip()
        full_cmd: list[str] | None = None
        if user_parts and not user_parts[0].startswith("-"):
            full_cmd = user_parts

        agent_args_record = ""
        if full_cmd is not None:
            agent_args_record = " ".join(full_cmd).strip()
        else:
            agent_args_record = " ".join([*env_agent_args, *user_parts]).strip()

        docker_inner_cmd, verify_agent = build_interactive_container_command(
            agent_cli=agent_cli,
            prompt=prompt,
            env_agent_args=env_agent_args,
            user_parts=user_parts if full_cmd is None else [],
            full_cmd=full_cmd,
            host_workdir=effective_workdir,
            gh_mode=gh_mode,
        )
        if not docker_inner_cmd:
            QMessageBox.warning(self, "Invalid command", "Could not build an interactive command to run.")
            return

        token: str | None = None
        if verify_agent == "copilot":
            token = resolve_github_token()

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env and env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        task_id = uuid4().hex[:10]
        container_name = f"codex-gui-it-{task_id}"
        image = PIXELARCH_EMERALD_IMAGE

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=effective_workdir,
            host_codex_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="pulling",
            container_id=container_name,
            gh_management_mode=gh_mode,
            agent_cli=agent_cli,
            agent_cli_args=agent_args_record,
        )
        task.gh_base_branch = str(base_branch or "").strip()
        use_host_gh = bool(getattr(env, "gh_use_host_cli", True)) if env else True
        task.gh_use_host_cli = bool(use_host_gh and is_gh_available())
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        stop = threading.Event()
        self._interactive_watch[task_id] = (container_name, stop)
        threading.Thread(
            target=self._watch_interactive_container,
            args=(task_id, container_name, stop),
            daemon=True,
        ).start()

        script, cwd = build_interactive_terminal_script(
            task_id=task_id,
            container_name=container_name,
            image=image,
            config_agent_cli=agent_cli,
            verify_agent_cli=verify_agent,
            host_config_dir=host_codex,
            host_workdir=effective_workdir,
            extra_mounts=list(env.extra_mounts) if env else [],
            env_vars=dict(env.env_vars) if env else {},
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            launch_preflight_script=str(launch_preflight_script or ""),
            gh_repo=(str(env.gh_management_target or "").strip() if (env and gh_mode == GH_MANAGEMENT_GITHUB) else ""),
            gh_base_branch=str(base_branch or "").strip(),
            gh_prefer_gh=bool(getattr(env, "gh_use_host_cli", True)) if env else True,
            docker_inner_cmd=docker_inner_cmd,
            token=token,
        )

        try:
            launch_in_terminal(option, script, cwd=cwd)
        except Exception as exc:
            self._interactive_watch.pop(task_id, None)
            stop.set()
            QMessageBox.warning(self, "Failed to launch terminal", str(exc))
            return

        self._show_dashboard()
        self._new_task.reset_for_new_run()


    def _resolve_terminal_option(self, terminal_id: str) -> TerminalOption | None:
        terminal_id = str(terminal_id or "").strip()
        if not terminal_id:
            return None
        for opt in detect_terminal_options():
            if opt.terminal_id == terminal_id:
                return opt
        return None


    def _watch_interactive_container(self, task_id: str, container_id: str, stop: threading.Event) -> None:
        task_id = str(task_id or "").strip()
        container_id = str(container_id or "").strip()
        if not task_id or not container_id:
            return

        started = False
        try:
            while not stop.is_set():
                try:
                    state = _inspect_state(container_id)
                except Exception:
                    if started:
                        break
                    time.sleep(0.6)
                    continue

                started = True
                try:
                    self.host_state.emit(task_id, state)
                except Exception:
                    pass

                status = str(state.get("Status") or "").lower()
                if status in {"exited", "dead"}:
                    break
                time.sleep(0.75)
        finally:
            self._interactive_watch.pop(task_id, None)

        if stop.is_set():
            return

        try:
            final_state = _inspect_state(container_id)
        except Exception:
            final_state = {"Status": "unknown"}
        try:
            self.host_state.emit(task_id, final_state)
        except Exception:
            pass

        try:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=25.0,
            )
        except Exception:
            pass
