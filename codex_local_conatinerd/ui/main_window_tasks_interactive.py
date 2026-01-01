from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time

from datetime import datetime
from datetime import timezone
from uuid import uuid4

from PySide6.QtCore import Qt

from PySide6.QtWidgets import QMessageBox

from codex_local_conatinerd.agent_cli import additional_config_mounts
from codex_local_conatinerd.agent_cli import container_config_dir
from codex_local_conatinerd.agent_cli import normalize_agent
from codex_local_conatinerd.agent_cli import verify_cli_clause
from codex_local_conatinerd.docker_platform import ROSETTA_INSTALL_COMMAND
from codex_local_conatinerd.docker_platform import docker_platform_args_for_pixelarch
from codex_local_conatinerd.docker_platform import has_rosetta
from codex_local_conatinerd.environments import Environment
from codex_local_conatinerd.environments import GH_MANAGEMENT_GITHUB
from codex_local_conatinerd.environments import GH_MANAGEMENT_LOCAL
from codex_local_conatinerd.environments import GH_MANAGEMENT_NONE
from codex_local_conatinerd.environments import normalize_gh_management_mode
from codex_local_conatinerd.gh_management import ensure_github_clone
from codex_local_conatinerd.gh_management import is_gh_available
from codex_local_conatinerd.gh_management import is_git_repo
from codex_local_conatinerd.gh_management import plan_repo_task
from codex_local_conatinerd.gh_management import prepare_branch_for_task
from codex_local_conatinerd.gh_management import GhManagementError
from codex_local_conatinerd.prompt_sanitizer import sanitize_prompt
from codex_local_conatinerd.terminal_apps import detect_terminal_options
from codex_local_conatinerd.terminal_apps import launch_in_terminal
from codex_local_conatinerd.ui.constants import PIXELARCH_EMERALD_IMAGE
from codex_local_conatinerd.ui.task_model import Task
from codex_local_conatinerd.ui.utils import _safe_str
from codex_local_conatinerd.ui.utils import _stain_color


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
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return

        prompt = sanitize_prompt((prompt or "").strip())
        host_codex = os.path.expanduser((host_codex or "").strip())

        options = {opt.terminal_id: opt for opt in detect_terminal_options()}
        opt = options.get(str(terminal_id or "").strip())
        if opt is None:
            QMessageBox.warning(
                self,
                "Terminal not available",
                "The selected terminal could not be found. Click Refresh next to Terminal and pick again.",
            )
            return

        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(self, "Unknown environment", "Pick an environment first.")
            return
        env = self._environments.get(env_id)
        gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE)) if env else GH_MANAGEMENT_NONE
        host_workdir, ready, message = self._new_task_workspace(env)
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return

        task_id = uuid4().hex[:10]
        task_token = f"interactive-{task_id}"
        if gh_mode != GH_MANAGEMENT_GITHUB and not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        desired_base = str(base_branch or "").strip()

        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
                return

        raw_command = str(command or "").strip()
        if not raw_command:
            interactive_key = self._interactive_command_key(agent_cli)
            raw_command = str(self._settings_data.get(interactive_key) or "").strip()
            if not raw_command:
                raw_command = self._default_interactive_command(agent_cli)
        command = raw_command
        is_help_launch = self._is_agent_help_interactive_launch(prompt=prompt, command=command)
        if is_help_launch:
            prompt = "\n".join(
                [
                    f"You are running: `{agent_cli}` right now",
                    "",
                    str(prompt or "").strip(),
                ]
            ).strip()
        try:
            if command.startswith("-"):
                cmd_parts = [agent_cli, *shlex.split(command)]
            else:
                cmd_parts = shlex.split(command)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid container command", str(exc))
            return
        if not cmd_parts:
            cmd_parts = ["bash"]

        def _move_positional_to_end(parts: list[str], value: str) -> None:
            value = str(value or "")
            if not value:
                return
            for idx in range(len(parts) - 1, 0, -1):
                if parts[idx] != value:
                    continue
                prev = parts[idx - 1]
                if prev != "--" and prev.startswith("-"):
                    continue
                parts.pop(idx)
                break
            parts.append(value)

        def _move_flag_value_to_end(parts: list[str], flags: set[str]) -> None:
            for idx in range(len(parts) - 2, -1, -1):
                if parts[idx] in flags:
                    flag = parts.pop(idx)
                    value = parts.pop(idx)
                    parts.extend([flag, value])
                    return

        if cmd_parts[0] == "codex":
            if len(cmd_parts) >= 2 and cmd_parts[1] == "exec":
                cmd_parts.pop(1)
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if prompt:
                _move_positional_to_end(cmd_parts, prompt)
        elif cmd_parts[0] == "claude":
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if "--add-dir" not in cmd_parts:
                cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]
            if prompt:
                _move_positional_to_end(cmd_parts, prompt)
        elif cmd_parts[0] == "copilot":
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if "--add-dir" not in cmd_parts:
                cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]
            if prompt:
                has_interactive = "-i" in cmd_parts or "--interactive" in cmd_parts
                has_prompt = "-p" in cmd_parts or "--prompt" in cmd_parts
                if has_prompt:
                    _move_flag_value_to_end(cmd_parts, {"-p", "--prompt"})
                elif not has_interactive:
                    cmd_parts.extend(["-i", prompt])

        image = PIXELARCH_EMERALD_IMAGE

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

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
            gh_management_mode=gh_mode,
            gh_use_host_cli=bool(getattr(env, "gh_use_host_cli", True)) if env else True,
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        task.gh_use_host_cli = bool(task.gh_use_host_cli and is_gh_available())
        if gh_mode == GH_MANAGEMENT_GITHUB and env:
            self._on_task_log(task_id, f"[gh] cloning {env.gh_management_target} -> {host_workdir}")
            try:
                os.makedirs(host_workdir, exist_ok=True)
            except Exception:
                pass
            try:
                ensure_github_clone(
                    str(env.gh_management_target or ""),
                    host_workdir,
                    prefer_gh=bool(task.gh_use_host_cli),
                    recreate_if_needed=True,
                )
            except GhManagementError as exc:
                task.status = "failed"
                task.error = str(exc)
                task.exit_code = 1
                task.finished_at = datetime.now(tz=timezone.utc)
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                self._details.update_task(task)
                self._schedule_save()
                QMessageBox.warning(self, "Failed to clone repo", str(exc))
                return

        if gh_mode == GH_MANAGEMENT_GITHUB and is_git_repo(host_workdir):
            plan = plan_repo_task(host_workdir, task_id=task_id, base_branch=desired_base or None)
            if plan is not None:
                self._on_task_log(task_id, f"[gh] creating branch {plan.branch} (base {plan.base_branch})")
                try:
                    base_branch, branch = prepare_branch_for_task(
                        plan.repo_root,
                        branch=plan.branch,
                        base_branch=plan.base_branch,
                    )
                except GhManagementError as exc:
                    task.status = "failed"
                    task.error = str(exc)
                    task.exit_code = 1
                    task.finished_at = datetime.now(tz=timezone.utc)
                    self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                    self._details.update_task(task)
                    self._schedule_save()
                    QMessageBox.warning(self, "Failed to create branch", str(exc))
                    return
                task.gh_repo_root = plan.repo_root
                task.gh_base_branch = base_branch
                task.gh_branch = branch
                self._schedule_save()
        elif gh_mode == GH_MANAGEMENT_GITHUB and desired_base and is_git_repo(host_workdir):
            proc = subprocess.run(
                ["git", "-C", host_workdir, "checkout", desired_base],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                msg = (proc.stderr or proc.stdout or "").strip() or f"git checkout {desired_base} failed"
                task.status = "failed"
                task.error = msg
                task.exit_code = 1
                task.finished_at = datetime.now(tz=timezone.utc)
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                self._details.update_task(task)
                self._schedule_save()
                QMessageBox.warning(self, "Failed to checkout base branch", msg)
                return

        settings_tmp_path = ""
        env_tmp_path = ""
        helpme_tmp_path = ""

        preflight_clause = ""
        preflight_mounts: list[str] = []
        settings_container_path = f"/tmp/codex-preflight-settings-{task_token}.sh"
        environment_container_path = f"/tmp/codex-preflight-environment-{task_token}.sh"
        helpme_container_path = f"/tmp/codex-preflight-helpme-{task_token}.sh"

        def _write_preflight_script(script: str, label: str) -> str:
            fd, tmp_path = tempfile.mkstemp(prefix=f"codex-preflight-{label}-{task_token}-", suffix=".sh")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    if not script.endswith("\n"):
                        script += "\n"
                    f.write(script)
            except Exception:
                try:
                    os.close(fd)
                except Exception:
                    pass
                raise
            return tmp_path

        try:
            if (settings_preflight_script or "").strip():
                settings_tmp_path = _write_preflight_script(str(settings_preflight_script or ""), "settings")
                preflight_mounts.extend(["-v", f"{settings_tmp_path}:{settings_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_SETTINGS={shlex.quote(settings_container_path)}; '
                    'echo "[preflight] settings: running"; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    'echo "[preflight] settings: done"; '
                )

            if (environment_preflight_script or "").strip():
                env_tmp_path = _write_preflight_script(str(environment_preflight_script or ""), "environment")
                preflight_mounts.extend(["-v", f"{env_tmp_path}:{environment_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_ENV={shlex.quote(environment_container_path)}; '
                    'echo "[preflight] environment: running"; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    'echo "[preflight] environment: done"; '
                )

            if str(extra_preflight_script or "").strip():
                helpme_tmp_path = _write_preflight_script(str(extra_preflight_script or ""), "helpme")
                preflight_mounts.extend(["-v", f"{helpme_tmp_path}:{helpme_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_HELP={shlex.quote(helpme_container_path)}; '
                    'echo "[preflight] helpme: running"; '
                    '/bin/bash "${PREFLIGHT_HELP}"; '
                    'echo "[preflight] helpme: done"; '
                )
        except Exception as exc:
            for tmp in (settings_tmp_path, env_tmp_path, helpme_tmp_path):
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            task.status = "failed"
            task.error = str(exc)
            task.exit_code = 1
            task.finished_at = datetime.now(tz=timezone.utc)
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            QMessageBox.warning(self, "Failed to prepare preflight scripts", str(exc))
            return

        try:
            env_args: list[str] = []
            for key, value in sorted((env.env_vars or {}).items() if env else []):
                k = str(key).strip()
                if not k:
                    continue
                env_args.extend(["-e", f"{k}={value}"])

            extra_mount_args: list[str] = []
            for mount in (env.extra_mounts or []) if env else []:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])
            for mount in config_extra_mounts:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])

            target_cmd = " ".join(shlex.quote(part) for part in cmd_parts)
            verify_clause = ""
            if cmd_parts[0] in {"codex", "claude", "copilot"}:
                verify_clause = verify_cli_clause(cmd_parts[0])

            container_script = "set -euo pipefail; " f"{preflight_clause}{verify_clause}{target_cmd}"

            forward_gh_token = bool(cmd_parts and cmd_parts[0] == "copilot")
            docker_env_passthrough: list[str] = []
            if forward_gh_token:
                docker_env_passthrough = ["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"]

            docker_platform_args = docker_platform_args_for_pixelarch()
            docker_args = [
                "docker",
                "run",
                *docker_platform_args,
                "-it",
                "--name",
                container_name,
                "-v",
                f"{host_codex}:{container_agent_dir}",
                "-v",
                f"{host_workdir}:{container_workdir}",
                *extra_mount_args,
                *preflight_mounts,
                *env_args,
                *docker_env_passthrough,
                "-w",
                container_workdir,
                image,
                "/bin/bash",
                "-lc",
                container_script,
            ]
            docker_cmd = " ".join(shlex.quote(part) for part in docker_args)

            finish_dir = os.path.dirname(self._state_path)
            os.makedirs(finish_dir, exist_ok=True)
            finish_path = os.path.join(finish_dir, f"interactive-finish-{task_id}.txt")
            try:
                if os.path.exists(finish_path):
                    os.unlink(finish_path)
            except Exception:
                pass

            gh_token_snippet = ""
            if forward_gh_token:
                gh_token_snippet = (
                    'if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then '
                    'TOKEN="$(gh auth token -h github.com 2>/dev/null || true)"; '
                    'TOKEN="$(printf "%s" "$TOKEN" | tr -d "\\r\\n")"; '
                    'if [ -n "$TOKEN" ]; then export GH_TOKEN="$TOKEN"; export GITHUB_TOKEN="$TOKEN"; fi; '
                    "fi"
                )

            rosetta_snippet = ""
            if has_rosetta() is False:
                rosetta_snippet = (
                    f'echo "[host] Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}"'
                )

            docker_pull_parts = ["docker", "pull", *docker_platform_args, image]
            docker_pull_cmd = " ".join(shlex.quote(part) for part in docker_pull_parts)

            host_script_parts = [
                    f'CONTAINER_NAME={shlex.quote(container_name)}',
                    f'TMP_SETTINGS={shlex.quote(settings_tmp_path)}',
                    f'TMP_ENV={shlex.quote(env_tmp_path)}',
                    f'TMP_HELPME={shlex.quote(helpme_tmp_path)}',
                    f'FINISH_FILE={shlex.quote(finish_path)}',
                    'write_finish() { STATUS="${1:-0}"; printf "%s\\n" "$STATUS" >"$FINISH_FILE" 2>/dev/null || true; }',
                    'cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; '
                    'if [ -n "$TMP_SETTINGS" ]; then rm -f -- "$TMP_SETTINGS" >/dev/null 2>&1 || true; fi; '
                    'if [ -n "$TMP_ENV" ]; then rm -f -- "$TMP_ENV" >/dev/null 2>&1 || true; fi; '
                    'if [ -n "$TMP_HELPME" ]; then rm -f -- "$TMP_HELPME" >/dev/null 2>&1 || true; fi; }',
                    'finish() { STATUS=$?; if [ ! -e "$FINISH_FILE" ]; then write_finish "$STATUS"; fi; cleanup; }',
                    "trap finish EXIT",
                ]
            if gh_token_snippet:
                host_script_parts.append(gh_token_snippet)
            if rosetta_snippet:
                host_script_parts.append(rosetta_snippet)
            host_script_parts.extend(
                [
                    f"{docker_pull_cmd} || {{ STATUS=$?; echo \"[host] docker pull failed (exit $STATUS)\"; write_finish \"$STATUS\"; read -r -p \"Press Enter to close...\"; exit $STATUS; }}",
                    f"{docker_cmd}; STATUS=$?; if [ $STATUS -ne 0 ]; then echo \"[host] container command failed (exit $STATUS)\"; fi; write_finish \"$STATUS\"; if [ $STATUS -ne 0 ]; then read -r -p \"Press Enter to close...\"; fi; exit $STATUS",
                ]
            )
            host_script = " ; ".join(host_script_parts)

            self._settings_data["host_workdir"] = host_workdir
            self._settings_data[self._host_config_dir_key(agent_cli)] = host_codex
            self._settings_data["active_environment_id"] = env_id
            self._settings_data["interactive_terminal_id"] = str(terminal_id or "")
            interactive_key = self._interactive_command_key(agent_cli)
            if not self._is_agent_help_interactive_launch(prompt=prompt, command=command):
                self._settings_data[interactive_key] = self._sanitize_interactive_command_value(interactive_key, command)
            self._apply_active_environment_to_new_task()
            self._schedule_save()

            task.status = "running"
            task.started_at = datetime.now(tz=timezone.utc)
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            self._start_interactive_finish_watch(task_id, finish_path)
            self._on_task_log(task_id, f"[interactive] launched in {opt.label}")

            launch_in_terminal(opt, host_script, cwd=host_workdir)
            self._show_dashboard()
            self._new_task.reset_for_new_run()
        except Exception as exc:
            for tmp in (settings_tmp_path, env_tmp_path, helpme_tmp_path):
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            task.status = "failed"
            task.error = str(exc)
            task.exit_code = 1
            task.finished_at = datetime.now(tz=timezone.utc)
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            QMessageBox.warning(self, "Failed to launch terminal", str(exc))


    def _start_interactive_finish_watch(self, task_id: str, finish_path: str) -> None:
        task_id = str(task_id or "").strip()
        finish_path = os.path.abspath(os.path.expanduser(str(finish_path or "").strip()))
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
