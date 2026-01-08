"""Docker launcher for interactive agent tasks.

This module handles Docker command construction, preflight script preparation,
and terminal script generation for launching interactive agent tasks.
"""

from __future__ import annotations

import os
import shlex
import socket
from datetime import datetime
from datetime import timezone

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import verify_cli_clause
from agents_runner.docker_platform import ROSETTA_INSTALL_COMMAND
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.docker_platform import has_rosetta
from agents_runner.environments import Environment
from agents_runner.terminal_apps import launch_in_terminal
from agents_runner.ui.docker_launch_helpers import _build_docker_command
from agents_runner.ui.docker_launch_helpers import _build_host_shell_script
from agents_runner.ui.docker_launch_helpers import _cleanup_temp_files
from agents_runner.ui.docker_launch_helpers import _prepare_preflight_scripts
from agents_runner.ui.shell_templates import build_git_clone_or_update_snippet
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _safe_str


def launch_docker_terminal_task(
    main_window: object,
    task: Task,
    env: Environment | None,
    env_id: str,
    task_id: str,
    task_token: str,
    terminal_opt: object,
    cmd_parts: list[str],
    prompt: str,
    command: str,
    agent_cli: str,
    host_codex: str,
    host_workdir: str,
    config_extra_mounts: list[str],
    image: str,
    container_name: str,
    container_agent_dir: str,
    container_workdir: str,
    settings_preflight_script: str | None,
    environment_preflight_script: str | None,
    extra_preflight_script: str,
    stain: str | None,
    spinner: str | None,
    desired_base: str = "",
    gh_repo: str = "",
    gh_prefer_gh_cli: bool = True,
) -> None:
    """Construct Docker command, generate host shell script, and launch terminal.

    Handles:
    - Preflight script preparation and mounting
    - Docker run command construction
    - Environment variables and port mapping
    - Git clone/update script generation
    - Terminal launcher invocation
    - Error handling and cleanup

    Args:
        main_window: MainWindow instance for callbacks and state access
        task: Task model object
        env: Environment object or None
        env_id: Environment ID
        task_id: Task ID
        task_token: Unique task token for temp files
        terminal_opt: Terminal option object
        cmd_parts: Command parts list
        prompt: User prompt
        command: Raw command string
        agent_cli: Agent CLI name
        host_codex: Host config directory path
        host_workdir: Host workspace directory path
        config_extra_mounts: Additional config mounts
        image: Docker image name
        container_name: Container name
        container_agent_dir: Container config directory path
        container_workdir: Container workspace directory path
        settings_preflight_script: Global preflight script
        environment_preflight_script: Environment-specific preflight script
        extra_preflight_script: Additional preflight script (help mode, etc.)
        stain: Task color stain
        spinner: Task spinner color
        desired_base: Desired base branch for git
        gh_repo: GitHub repository (owner/repo)
        gh_prefer_gh_cli: Prefer gh CLI over git for cloning
    """
    # Prepare preflight scripts and get mounts
    preflight_clause, preflight_mounts, tmp_paths = _prepare_preflight_scripts(
        task_token=task_token,
        settings_preflight_script=settings_preflight_script,
        environment_preflight_script=environment_preflight_script,
        extra_preflight_script=extra_preflight_script,
    )

    if preflight_clause is None:
        # Error during preflight preparation
        _handle_launch_error(
            main_window, task, tmp_paths, stain, spinner,
            "Failed to prepare preflight scripts"
        )
        return

    try:
        # Collect environment variables
        env_args: list[str] = []
        for key, value in sorted((env.env_vars or {}).items() if env else []):
            k = str(key).strip()
            if not k:
                continue
            env_args.extend(["-e", f"{k}={value}"])

        # Check if desktop mode is enabled
        desktop_enabled = (
            "websockify" in extra_preflight_script
            or "noVNC" in extra_preflight_script
            or "[desktop]" in extra_preflight_script
        )

        # Allocate port for desktop mode
        port_args: list[str] = []
        if desktop_enabled:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(("127.0.0.1", 0))
                host_port = int(s.getsockname()[1])
            finally:
                s.close()
            port_args = ["-p", f"127.0.0.1:{host_port}:6080"]
            env_args.extend(["-e", f"AGENTS_RUNNER_TASK_ID={task_token}"])
            task.headless_desktop_enabled = True
            task.desktop_display = ":1"
            task.novnc_url = f"http://127.0.0.1:{host_port}/vnc.html"
            main_window._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            main_window._details.update_task(task)
            main_window._schedule_save()

        # Prepare extra mounts
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

        # Build container script with preflight and command
        target_cmd = " ".join(shlex.quote(part) for part in cmd_parts)
        verify_clause = ""
        if cmd_parts[0] in {"codex", "claude", "copilot", "gemini"}:
            verify_clause = verify_cli_clause(cmd_parts[0])

        container_script = (
            "set -euo pipefail; " f"{preflight_clause}{verify_clause}{target_cmd}"
        )

        # Check if we need to forward GH_TOKEN
        forward_gh_token = bool(cmd_parts and cmd_parts[0] == "copilot")
        docker_env_passthrough: list[str] = []
        if forward_gh_token:
            docker_env_passthrough = ["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"]

        # Build Docker command
        docker_cmd = _build_docker_command(
            container_name=container_name,
            host_codex=host_codex,
            host_workdir=host_workdir,
            container_agent_dir=container_agent_dir,
            container_workdir=container_workdir,
            extra_mount_args=extra_mount_args,
            preflight_mounts=preflight_mounts,
            env_args=env_args,
            port_args=port_args,
            docker_env_passthrough=docker_env_passthrough,
            image=image,
            container_script=container_script,
        )

        # Prepare finish file for exit code tracking
        finish_dir = os.path.dirname(main_window._state_path)
        os.makedirs(finish_dir, exist_ok=True)
        finish_path = os.path.join(finish_dir, f"interactive-finish-{task_id}.txt")
        try:
            if os.path.exists(finish_path):
                os.unlink(finish_path)
        except Exception:
            # Best-effort cleanup: ignore errors while removing stale finish file.
            pass

        # Build git token snippet
        gh_token_snippet = ""
        if forward_gh_token:
            gh_token_snippet = (
                'if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then '
                'TOKEN="$(gh auth token -h github.com 2>/dev/null || true)"; '
                'TOKEN="$(printf "%s" "$TOKEN" | tr -d "\\r\\n")"; '
                'if [ -n "$TOKEN" ]; then export GH_TOKEN="$TOKEN"; export GITHUB_TOKEN="$TOKEN"; fi; '
                "fi"
            )

        # Build Rosetta warning snippet
        rosetta_snippet = ""
        if has_rosetta() is False:
            rosetta_snippet = f'echo "[host] Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}"'

        # Build git clone snippet if gh_repo is specified
        gh_clone_snippet = ""
        if gh_repo:
            quoted_dest = shlex.quote(host_workdir)
            gh_clone_snippet = build_git_clone_or_update_snippet(
                gh_repo=gh_repo,
                host_workdir=host_workdir,
                quoted_dest=quoted_dest,
                prefer_gh_cli=gh_prefer_gh_cli,
                task_id=task_id,
                desired_base=desired_base,
                is_locked_env=False,
            )
            # Update task with branch info
            branch_name = f"agents-runner-{task_id}"
            task.gh_repo_root = host_workdir
            task.gh_branch = branch_name
            task.gh_base_branch = desired_base
            main_window._schedule_save()

        # Build docker pull command
        docker_platform_args = docker_platform_args_for_pixelarch()
        docker_pull_parts = ["docker", "pull", *docker_platform_args, image]
        docker_pull_cmd = " ".join(shlex.quote(part) for part in docker_pull_parts)

        # Build host shell script
        host_script = _build_host_shell_script(
            container_name=container_name,
            task_token=task_token,
            tmp_paths=tmp_paths,
            finish_path=finish_path,
            gh_token_snippet=gh_token_snippet,
            rosetta_snippet=rosetta_snippet,
            gh_clone_snippet=gh_clone_snippet,
            docker_pull_cmd=docker_pull_cmd,
            docker_cmd=docker_cmd,
        )

        # Log base branch if specified
        if (desired_base or "").strip():
            main_window._on_task_log(task_id, f"[gh] base branch: {desired_base}")

        # Update settings
        main_window._settings_data["host_workdir"] = host_workdir
        main_window._settings_data[main_window._host_config_dir_key(agent_cli)] = host_codex
        main_window._settings_data["active_environment_id"] = env_id
        main_window._settings_data["interactive_terminal_id"] = str(
            getattr(terminal_opt, "terminal_id", "")
        )
        interactive_key = main_window._interactive_command_key(agent_cli)
        if not main_window._is_agent_help_interactive_launch(
            prompt=prompt, command=command
        ):
            main_window._settings_data[interactive_key] = (
                main_window._sanitize_interactive_command_value(interactive_key, command)
            )
        main_window._apply_active_environment_to_new_task()
        main_window._schedule_save()

        # Update task status to running
        task.status = "running"
        task.started_at = datetime.now(tz=timezone.utc)
        main_window._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        main_window._details.update_task(task)
        main_window._schedule_save()

        # Start finish file watcher
        main_window._start_interactive_finish_watch(task_id, finish_path)

        # Log launch
        main_window._on_task_log(
            task_id,
            f"[interactive] launched in {_safe_str(getattr(terminal_opt, 'label', 'Terminal'))}",
        )

        # Launch terminal
        launch_in_terminal(terminal_opt, host_script, cwd=host_workdir)
        main_window._show_dashboard()
        main_window._new_task.reset_for_new_run()

    except Exception as exc:
        _handle_launch_error(
            main_window, task, tmp_paths, stain, spinner, str(exc)
        )


def _handle_launch_error(
    main_window: object,
    task: Task,
    tmp_paths: dict[str, str],
    stain: str | None,
    spinner: str | None,
    error_message: str,
) -> None:
    """Handle launch error by cleaning up and updating task status.

    Args:
        main_window: MainWindow instance
        task: Task model object
        tmp_paths: Dict of temp file paths to clean up
        stain: Task color stain
        spinner: Task spinner color
        error_message: Error message to display
    """
    _cleanup_temp_files(tmp_paths)
    task.status = "failed"
    task.error = error_message
    task.exit_code = 1
    task.finished_at = datetime.now(tz=timezone.utc)
    main_window._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
    main_window._details.update_task(task)
    main_window._schedule_save()
    QMessageBox.warning(main_window, "Failed to launch terminal", error_message)
