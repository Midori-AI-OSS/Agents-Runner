"""Docker launcher for interactive agent tasks (Version 2).

New lifecycle:
1. App creates staging directory and writes entrypoint script
2. App starts container detached with -dit --rm
3. App starts log tail immediately
4. App starts docker wait monitor thread
5. Terminal attaches to running container
6. On exit, completion marker is read from staging directory
"""

from __future__ import annotations

import os
import shlex
import socket
import subprocess
import tempfile
from datetime import datetime
from datetime import timezone
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import verify_cli_clause
from agents_runner.docker_platform import ROSETTA_INSTALL_COMMAND
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.docker_platform import has_rosetta
from agents_runner.environments import Environment
from agents_runner.github_token import resolve_github_token
from agents_runner.log_format import format_log
from agents_runner.terminal_apps import launch_in_terminal
from agents_runner.ui.shell_templates import build_git_clone_or_update_snippet
from agents_runner.ui.shell_templates import git_identity_clause
from agents_runner.ui.shell_templates import shell_log_statement
from agents_runner.ui.task_model import Task
from agents_runner.ui.task_staging import ensure_artifacts_staging_dir
from agents_runner.ui.task_staging import write_container_entrypoint_script
from agents_runner.ui.task_container_lifecycle import start_container_wait_monitor
from agents_runner.ui.task_container_lifecycle import launch_attach_terminal
from agents_runner.ui.utils import _safe_str


def launch_docker_terminal_task_v2(
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
    """Launch interactive task with app-owned container lifecycle (v2).
    
    New workflow:
    1. Create artifacts staging directory
    2. Write container entrypoint script to staging
    3. Start container detached with -dit --rm
    4. Mount staging directory to /tmp/agents-artifacts
    5. Start log tail immediately
    6. Start docker wait monitor thread
    7. Launch terminal with docker attach
    
    Args: (same as v1)
    """
    # Mark task as interactive v2
    task.interactive_version = 2
    
    # Create artifacts staging directory
    try:
        staging_dir = ensure_artifacts_staging_dir(task_id)
        task.artifacts_staging_dir = str(staging_dir)
        main_window._schedule_save()
    except Exception as exc:
        _handle_launch_error_v2(
            main_window, task, stain, spinner,
            f"Failed to create staging directory: {exc}"
        )
        return
    
    # Prepare preflight scripts and get mounts
    from agents_runner.ui.main_window_tasks_interactive_docker import _prepare_preflight_scripts
    
    preflight_clause, preflight_mounts, tmp_paths = _prepare_preflight_scripts(
        task_token=task_token,
        settings_preflight_script=settings_preflight_script,
        environment_preflight_script=environment_preflight_script,
        extra_preflight_script=extra_preflight_script,
    )
    
    if preflight_clause is None:
        _handle_launch_error_v2(
            main_window, task, stain, spinner,
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
        
        # Forward GH_TOKEN if needed
        forward_gh_token = bool(
            (cmd_parts and cmd_parts[0] == "copilot")
            or (env and getattr(env, "gh_context_enabled", False))
        )
        if forward_gh_token:
            gh_token = resolve_github_token()
            if gh_token:
                env_args.extend(["-e", f"GH_TOKEN={gh_token}", "-e", f"GITHUB_TOKEN={gh_token}"])
        
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
        
        # Add host cache mount if enabled
        if main_window._settings_data.get("mount_host_cache", False):
            host_cache = os.path.expanduser("~/.cache")
            container_cache = "/home/midori-ai/.cache"
            extra_mount_args.extend(["-v", f"{host_cache}:{container_cache}:rw"])
        
        # Add environment-specific mounts
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
        
        # Write entrypoint script to staging directory
        container_script = (
            f"{git_identity_clause()}{preflight_clause}{verify_clause}{target_cmd}"
        )
        try:
            write_container_entrypoint_script(
                staging_dir=staging_dir,
                task_id=task_id,
                agent_cli_cmd=container_script,
            )
        except Exception as exc:
            _handle_launch_error_v2(
                main_window, task, stain, spinner,
                f"Failed to write entrypoint script: {exc}"
            )
            from agents_runner.ui.main_window_tasks_interactive_docker import _cleanup_temp_files
            _cleanup_temp_files(tmp_paths)
            return
        
        # Build Docker command (detached with -dit)
        docker_platform_args = docker_platform_args_for_pixelarch()
        docker_cmd = [
            "docker",
            "run",
            *docker_platform_args,
            "--rm",
            "-dit",
            "--name",
            container_name,
            "-v",
            f"{staging_dir}:/tmp/agents-artifacts",
            "-v",
            f"{host_codex}:{container_agent_dir}",
            "-v",
            f"{host_workdir}:{container_workdir}",
            *extra_mount_args,
            *preflight_mounts,
            *env_args,
            *port_args,
            "-w",
            container_workdir,
            image,
            "/bin/bash",
            "-lc",
            "/tmp/agents-artifacts/.container-entrypoint.sh",
        ]
        
        # Handle git clone if gh_repo specified
        if gh_repo:
            # Build git clone snippet
            quoted_dest = shlex.quote(host_workdir)
            from agents_runner.ui.shell_templates import build_git_clone_or_update_snippet
            
            gh_clone_snippet = build_git_clone_or_update_snippet(
                gh_repo=gh_repo,
                host_workdir=host_workdir,
                quoted_dest=quoted_dest,
                prefer_gh_cli=gh_prefer_gh_cli,
                task_id=task_id,
                desired_base=desired_base,
                is_locked_env=False,
            )
            
            # Execute git clone on host (before container start)
            try:
                subprocess.run(
                    ["/bin/bash", "-c", gh_clone_snippet],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                _handle_launch_error_v2(
                    main_window, task, stain, spinner,
                    f"Git clone failed: {exc.stderr}"
                )
                from agents_runner.ui.main_window_tasks_interactive_docker import _cleanup_temp_files
                _cleanup_temp_files(tmp_paths)
                return
            
            # Update task with branch info
            branch_name = f"agents-runner-{task_id}"
            task.gh_repo_root = host_workdir
            task.gh_branch = branch_name
            task.gh_base_branch = desired_base
            main_window._schedule_save()
        
        # Pull Docker image
        docker_pull_cmd = ["docker", "pull", *docker_platform_args, image]
        try:
            result = subprocess.run(
                docker_pull_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"docker pull failed: {result.stderr}")
        except Exception as exc:
            _handle_launch_error_v2(
                main_window, task, stain, spinner,
                f"Failed to pull image: {exc}"
            )
            from agents_runner.ui.main_window_tasks_interactive_docker import _cleanup_temp_files
            _cleanup_temp_files(tmp_paths)
            return
        
        # Log base branch if specified
        if (desired_base or "").strip():
            main_window._on_task_log(
                task_id, format_log("gh", "branch", "INFO", f"base branch: {desired_base}")
            )
        
        # Start container (detached)
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"docker run failed: {result.stderr}")
        except Exception as exc:
            _handle_launch_error_v2(
                main_window, task, stain, spinner,
                f"Failed to start container: {exc}"
            )
            from agents_runner.ui.main_window_tasks_interactive_docker import _cleanup_temp_files
            _cleanup_temp_files(tmp_paths)
            return
        
        # Container started successfully
        # Clean up temp preflight files
        from agents_runner.ui.main_window_tasks_interactive_docker import _cleanup_temp_files
        _cleanup_temp_files(tmp_paths)
        
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
        
        # Start log tail
        main_window._ensure_recovery_log_tail(task)
        
        # Start docker wait monitor
        start_container_wait_monitor(
            main_window=main_window,
            task_id=task_id,
            container_name=container_name,
        )
        
        # Launch terminal with docker attach
        main_window._on_task_log(
            task_id,
            format_log(
                "ui", "launch", "INFO",
                f"launched in {_safe_str(getattr(terminal_opt, 'label', 'Terminal'))}"
            ),
        )
        
        # Use the attach helper
        attach_success = launch_attach_terminal(
            terminal_opt=terminal_opt,
            container_name=container_name,
            host_workdir=host_workdir,
        )
        
        if not attach_success:
            main_window._on_task_log(
                task_id,
                format_log(
                    "ui", "attach", "WARN",
                    f"Failed to launch terminal; manually attach with: docker attach {container_name}"
                ),
            )
        
        # Show dashboard and reset new task form
        main_window._show_dashboard()
        main_window._new_task.reset_for_new_run()
        
    except Exception as exc:
        _handle_launch_error_v2(
            main_window, task, stain, spinner, str(exc)
        )
        from agents_runner.ui.main_window_tasks_interactive_docker import _cleanup_temp_files
        _cleanup_temp_files(tmp_paths)


def _handle_launch_error_v2(
    main_window: object,
    task: Task,
    stain: str | None,
    spinner: str | None,
    error_message: str,
) -> None:
    """Handle launch error by updating task status (v2 - no temp file cleanup here)."""
    task.status = "failed"
    task.error = error_message
    task.exit_code = 1
    task.finished_at = datetime.now(tz=timezone.utc)
    main_window._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
    main_window._details.update_task(task)
    main_window._schedule_save()
    QMessageBox.warning(main_window, "Failed to launch terminal", error_message)
