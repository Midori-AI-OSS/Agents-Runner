"""Docker launcher for interactive agent tasks.

This module handles Docker command construction, preflight script preparation,
and terminal script generation for launching interactive agent tasks.
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
from agents_runner.artifacts import get_staging_dir
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

        # Check if we need to forward GH_TOKEN
        forward_gh_token = bool(
            (cmd_parts and cmd_parts[0] == "copilot")
            or (env and getattr(env, "gh_context_enabled", False))
        )
        if forward_gh_token:
            gh_token = resolve_github_token()
            if gh_token:
                env_args.extend([f"-e", f"GH_TOKEN={gh_token}", f"-e", f"GITHUB_TOKEN={gh_token}"])

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
        
        # Create and mount staging directory for artifacts and completion markers
        artifacts_staging_dir = get_staging_dir(task_id)
        artifacts_staging_dir.mkdir(parents=True, exist_ok=True)
        extra_mount_args.extend(["-v", f"{artifacts_staging_dir}:/tmp/agents-artifacts"])
        
        # Add host cache mount if enabled in settings
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

        # Build completion marker function
        marker_script = _build_completion_marker_script(task_id, container_name)

        container_script = (
            "set -euo pipefail; "
            f"{marker_script}"
            f"{git_identity_clause()}{preflight_clause}{verify_clause}{target_cmd}"
        )

        # Build Docker command for detached launch
        docker_cmd_parts = _build_docker_command_parts(
            container_name=container_name,
            host_codex=host_codex,
            host_workdir=host_workdir,
            container_agent_dir=container_agent_dir,
            container_workdir=container_workdir,
            extra_mount_args=extra_mount_args,
            preflight_mounts=preflight_mounts,
            env_args=env_args,
            port_args=port_args,
            docker_env_passthrough=[],
            image=image,
            container_script=container_script,
            detached=True,
        )

        # Build Rosetta warning snippet
        rosetta_snippet = ""
        if has_rosetta() is False:
            rosetta_snippet = shell_log_statement("host", "docker", "WARN", f"Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}")

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

        # Pull Docker image (app-side)
        docker_platform_args = docker_platform_args_for_pixelarch()
        docker_pull_parts = ["docker", "pull", *docker_platform_args, image]
        main_window._on_task_log(
            task_id, format_log("docker", "pull", "INFO", f"pulling image {image}")
        )
        try:
            subprocess.run(
                docker_pull_parts,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"docker pull failed: {e.stderr.strip() if e.stderr else str(e)}"
            _handle_launch_error(
                main_window, task, tmp_paths, stain, spinner, error_msg
            )
            return

        # Launch container detached (app-side)
        main_window._on_task_log(
            task_id, format_log("docker", "launch", "INFO", f"starting container {container_name}")
        )
        try:
            subprocess.run(
                docker_cmd_parts,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"docker run failed: {e.stderr.strip() if e.stderr else str(e)}"
            _handle_launch_error(
                main_window, task, tmp_paths, stain, spinner, error_msg
            )
            return

        # Verify container is running
        try:
            inspect_result = subprocess.run(
                ["docker", "inspect", "--format={{.State.Running}}", container_name],
                check=True,
                capture_output=True,
                text=True,
            )
            is_running = inspect_result.stdout.strip().lower() == "true"
            if not is_running:
                error_msg = f"container {container_name} started but is not running"
                _handle_launch_error(
                    main_window, task, tmp_paths, stain, spinner, error_msg
                )
                return
        except subprocess.CalledProcessError as e:
            error_msg = f"failed to verify container state: {e.stderr.strip() if e.stderr else str(e)}"
            _handle_launch_error(
                main_window, task, tmp_paths, stain, spinner, error_msg
            )
            return

        # Store container name in task payload
        task.container_id = container_name

        # Build host shell script in attach mode
        host_script = _build_host_shell_script(
            container_name=container_name,
            task_token=task_token,
            tmp_paths=tmp_paths,
            gh_token_snippet="",
            rosetta_snippet=rosetta_snippet,
            gh_clone_snippet=gh_clone_snippet,
            attach_mode=True,
        )

        # Log base branch if specified
        if (desired_base or "").strip():
            main_window._on_task_log(
                task_id, format_log("gh", "branch", "INFO", f"base branch: {desired_base}")
            )

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

        # Start completion marker watcher
        main_window._start_interactive_finish_watch(task_id)

        # Log launch
        main_window._on_task_log(
            task_id,
            format_log(
                "ui", "launch", "INFO",
                f"launched in {_safe_str(getattr(terminal_opt, 'label', 'Terminal'))}"
            ),
        )

        # Launch terminal
        launch_in_terminal(terminal_opt, host_script, cwd=host_workdir)
        main_window._show_dashboard()
        main_window._new_task.reset_for_new_run()

    except Exception as exc:
        _handle_launch_error(
            main_window, task, tmp_paths, stain, spinner, str(exc)
        )


def _prepare_preflight_scripts(
    task_token: str,
    settings_preflight_script: str | None,
    environment_preflight_script: str | None,
    extra_preflight_script: str,
) -> tuple[str | None, list[str], dict[str, str]]:
    """Create temporary preflight script files and build mount args.

    Args:
        task_token: Unique task token for temp file naming
        settings_preflight_script: Global preflight script
        environment_preflight_script: Environment-specific preflight script
        extra_preflight_script: Additional preflight script

    Returns:
        Tuple of (preflight_clause, preflight_mounts, tmp_paths)
        - preflight_clause: Shell commands to execute preflights
        - preflight_mounts: Docker -v mount arguments
        - tmp_paths: Dict mapping label to temp file path for cleanup
        Returns (None, [], {}) on error
    """
    preflight_clause = ""
    preflight_mounts: list[str] = []
    tmp_paths: dict[str, str] = {
        "system": "",
        "settings": "",
        "environment": "",
        "helpme": "",
    }

    settings_container_path = f"/tmp/agents-runner-preflight-settings-{task_token}.sh"
    environment_container_path = f"/tmp/agents-runner-preflight-environment-{task_token}.sh"
    extra_container_path = f"/tmp/agents-runner-preflight-extra-{task_token}.sh"

    preflights_host_dir = (Path(__file__).resolve().parent.parent / "preflights").resolve()
    preflights_container_dir = "/tmp/agents-runner-preflights"

    def _write_preflight_script(script: str, label: str) -> str:
        """Write a preflight script to a temporary file."""
        fd, tmp_path = tempfile.mkstemp(
            prefix=f"agents-runner-preflight-{label}-{task_token}-", suffix=".sh"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                if not script.endswith("\n"):
                    script += "\n"
                f.write(script)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                # Best-effort cleanup: ignore errors while closing the fd,
                # since the original exception is re-raised below.
                pass
            raise
        return tmp_path

    try:
        if not preflights_host_dir.is_dir():
            raise RuntimeError(f"Missing preflights directory: {preflights_host_dir}")
        system_preflight_path = preflights_host_dir / "pixelarch_yay.sh"
        if not system_preflight_path.is_file():
            raise RuntimeError(f"Missing system preflight: {system_preflight_path}")

        # Mount the entire preflights directory (read-only) to avoid missing dependency scripts.
        preflight_mounts.extend(
            ["-v", f"{preflights_host_dir}:{preflights_container_dir}:ro"]
        )

        preflight_clause += (
            f"PREFLIGHTS_DIR={shlex.quote(preflights_container_dir)}; "
            'export AGENTS_RUNNER_PREFLIGHTS_DIR="${PREFLIGHTS_DIR}"; '
            'PREFLIGHT_SYSTEM="${PREFLIGHTS_DIR}/pixelarch_yay.sh"; '
            f'{shell_log_statement("docker", "preflight", "INFO", "system: starting")}; '
            '/bin/bash "${PREFLIGHT_SYSTEM}"; '
            f'{shell_log_statement("docker", "preflight", "INFO", "system: done")}; '
        )

        # Settings preflight (optional)
        if (settings_preflight_script or "").strip():
            preflights_scripts: dict[str, str] = {}
            try:
                for candidate in sorted(preflights_host_dir.glob("*.sh")):
                    preflights_scripts[candidate.name] = candidate.read_text(encoding="utf-8").strip()
            except Exception:
                preflights_scripts = {}

            stripped = str(settings_preflight_script or "").strip()
            matched = next(
                (
                    name
                    for name, content in preflights_scripts.items()
                    if content == stripped and name != "pixelarch_yay.sh"
                ),
                None,
            )
            if matched:
                preflight_clause += (
                    f'PREFLIGHT_SETTINGS="${{PREFLIGHTS_DIR}}/{matched}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "settings: running")}; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "settings: done")}; '
                )
            else:
                tmp_paths["settings"] = _write_preflight_script(
                    str(settings_preflight_script or ""), "settings"
                )
                preflight_mounts.extend(
                    ["-v", f"{tmp_paths['settings']}:{settings_container_path}:ro"]
                )
                preflight_clause += (
                    f"PREFLIGHT_SETTINGS={shlex.quote(settings_container_path)}; "
                    f'{shell_log_statement("docker", "preflight", "INFO", "settings: running")}; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "settings: done")}; '
                )

        # Environment preflight (optional)
        if (environment_preflight_script or "").strip():
            preflights_scripts = {}
            try:
                for candidate in sorted(preflights_host_dir.glob("*.sh")):
                    preflights_scripts[candidate.name] = candidate.read_text(encoding="utf-8").strip()
            except Exception:
                preflights_scripts = {}

            stripped = str(environment_preflight_script or "").strip()
            matched = next(
                (
                    name
                    for name, content in preflights_scripts.items()
                    if content == stripped and name != "pixelarch_yay.sh"
                ),
                None,
            )
            if matched:
                preflight_clause += (
                    f'PREFLIGHT_ENV="${{PREFLIGHTS_DIR}}/{matched}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "environment: running")}; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "environment: done")}; '
                )
            else:
                tmp_paths["environment"] = _write_preflight_script(
                    str(environment_preflight_script or ""), "environment"
                )
                preflight_mounts.extend(
                    ["-v", f"{tmp_paths['environment']}:{environment_container_path}:ro"]
                )
                preflight_clause += (
                    f"PREFLIGHT_ENV={shlex.quote(environment_container_path)}; "
                    f'{shell_log_statement("docker", "preflight", "INFO", "environment: running")}; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "environment: done")}; '
                )

        # Extra preflight (optional, help mode, etc.)
        if str(extra_preflight_script or "").strip():
            preflights_scripts = {}
            try:
                for candidate in sorted(preflights_host_dir.glob("*.sh")):
                    preflights_scripts[candidate.name] = candidate.read_text(encoding="utf-8").strip()
            except Exception:
                preflights_scripts = {}

            stripped = str(extra_preflight_script or "").strip()
            matched = next(
                (
                    name
                    for name, content in preflights_scripts.items()
                    if content == stripped and name != "pixelarch_yay.sh"
                ),
                None,
            )
            if matched:
                preflight_clause += (
                    f'PREFLIGHT_EXTRA="${{PREFLIGHTS_DIR}}/{matched}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "extra: running")}; '
                    '/bin/bash "${PREFLIGHT_EXTRA}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "extra: done")}; '
                )
            else:
                tmp_paths["helpme"] = _write_preflight_script(
                    str(extra_preflight_script or ""), "extra"
                )
                preflight_mounts.extend(
                    ["-v", f"{tmp_paths['helpme']}:{extra_container_path}:ro"]
                )
                preflight_clause += (
                    f"PREFLIGHT_EXTRA={shlex.quote(extra_container_path)}; "
                    f'{shell_log_statement("docker", "preflight", "INFO", "extra: running")}; '
                    '/bin/bash "${PREFLIGHT_EXTRA}"; '
                    f'{shell_log_statement("docker", "preflight", "INFO", "extra: done")}; '
                )

        return preflight_clause, preflight_mounts, tmp_paths

    except Exception:
        # Clean up any created temp files
        _cleanup_temp_files(tmp_paths)
        return None, [], tmp_paths


def _build_completion_marker_script(task_id: str, container_name: str) -> str:
    """Build shell script to write completion marker on EXIT.
    
    This generates a shell trap that writes a JSON completion marker when the
    container exits. The marker provides:
    - Container-side exit code (more accurate than host-side)
    - Precise start/finish timestamps from inside the container
    - Task and container identifiers for validation
    
    The marker is written to the mounted staging directory so it persists after
    the container is auto-removed. The host reads this marker to get accurate
    completion metadata from inside the container.
    
    Args:
        task_id: Task ID
        container_name: Container name

    Returns:
        Shell script with trap and marker writing function
    """
    # Escape quotes in task_id and container_name
    safe_task_id = shlex.quote(task_id)
    safe_container_name = shlex.quote(container_name)
    
    marker_function = (
        f'TASK_ID={safe_task_id}; '
        f'CONTAINER_NAME={safe_container_name}; '
        'STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); '
        'write_completion_marker() { '
        'EXIT_CODE=$?; '
        'FINISHED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); '
        'MARKER_FILE="/tmp/agents-artifacts/interactive-exit.json"; '
        'mkdir -p /tmp/agents-artifacts >/dev/null 2>&1 || true; '
        'cat > "$MARKER_FILE" <<EOF\n'
        '{\n'
        '  "task_id": "$TASK_ID",\n'
        '  "container_name": "$CONTAINER_NAME",\n'
        '  "exit_code": $EXIT_CODE,\n'
        '  "started_at": "$STARTED_AT",\n'
        '  "finished_at": "$FINISHED_AT",\n'
        '  "reason": "process_exit"\n'
        '}\n'
        'EOF\n'
        '}; '
        'trap write_completion_marker EXIT; '
    )
    return marker_function


def _build_docker_command(
    container_name: str,
    host_codex: str,
    host_workdir: str,
    container_agent_dir: str,
    container_workdir: str,
    extra_mount_args: list[str],
    preflight_mounts: list[str],
    env_args: list[str],
    port_args: list[str],
    docker_env_passthrough: list[str],
    image: str,
    container_script: str,
    detached: bool = False,
) -> str:
    """Build complete Docker run command string.

    Args:
        container_name: Container name
        host_codex: Host config directory path
        host_workdir: Host workspace directory path
        container_agent_dir: Container config directory path
        container_workdir: Container workspace directory path
        extra_mount_args: Additional mount arguments
        preflight_mounts: Preflight script mount arguments
        env_args: Environment variable arguments
        port_args: Port mapping arguments
        docker_env_passthrough: Environment passthrough arguments
        image: Docker image name
        container_script: Container script to execute
        detached: If True, use -dit (detached with interactive TTY); if False, use -it

    Returns:
        Complete Docker command string
    """
    docker_platform_args = docker_platform_args_for_pixelarch()
    
    # Choose flags based on detached mode
    mode_flags = ["-dit"] if detached else ["-it"]
    
    docker_args = [
        "docker",
        "run",
        *docker_platform_args,
        *mode_flags,
        "--rm",
        "--name",
        container_name,
        "-v",
        f"{host_codex}:{container_agent_dir}",
        "-v",
        f"{host_workdir}:{container_workdir}",
        *extra_mount_args,
        *preflight_mounts,
        *env_args,
        *port_args,
        *docker_env_passthrough,
        "-w",
        container_workdir,
        image,
        "/bin/bash",
        "-lc",
        container_script,
    ]
    return " ".join(shlex.quote(part) for part in docker_args)


def _build_docker_command_parts(
    container_name: str,
    host_codex: str,
    host_workdir: str,
    container_agent_dir: str,
    container_workdir: str,
    extra_mount_args: list[str],
    preflight_mounts: list[str],
    env_args: list[str],
    port_args: list[str],
    docker_env_passthrough: list[str],
    image: str,
    container_script: str,
    detached: bool = False,
) -> list[str]:
    """Build complete Docker run command as list of arguments.

    Args:
        container_name: Container name
        host_codex: Host config directory path
        host_workdir: Host workspace directory path
        container_agent_dir: Container config directory path
        container_workdir: Container workspace directory path
        extra_mount_args: Additional mount arguments
        preflight_mounts: Preflight script mount arguments
        env_args: Environment variable arguments
        port_args: Port mapping arguments
        docker_env_passthrough: Environment passthrough arguments
        image: Docker image name
        container_script: Container script to execute
        detached: If True, use -dit (detached with interactive TTY); if False, use -it

    Returns:
        Complete Docker command as list of arguments
    """
    docker_platform_args = docker_platform_args_for_pixelarch()
    
    # Choose flags based on detached mode
    mode_flags = ["-dit"] if detached else ["-it"]
    
    docker_args = [
        "docker",
        "run",
        *docker_platform_args,
        *mode_flags,
        "--rm",
        "--name",
        container_name,
        "-v",
        f"{host_codex}:{container_agent_dir}",
        "-v",
        f"{host_workdir}:{container_workdir}",
        *extra_mount_args,
        *preflight_mounts,
        *env_args,
        *port_args,
        *docker_env_passthrough,
        "-w",
        container_workdir,
        image,
        "/bin/bash",
        "-lc",
        container_script,
    ]
    return docker_args


def _build_host_shell_script(
    container_name: str,
    task_token: str,
    tmp_paths: dict[str, str],
    gh_token_snippet: str,
    rosetta_snippet: str,
    gh_clone_snippet: str,
    attach_mode: bool = False,
) -> str:
    """Build host-side shell script with cleanup and error handling.

    Args:
        container_name: Container name
        task_token: Unique task token
        tmp_paths: Dict of temp file paths for cleanup
        gh_token_snippet: GH token setup snippet
        rosetta_snippet: Rosetta warning snippet
        gh_clone_snippet: Git clone/update snippet
        attach_mode: If True, attach to existing container; if False, legacy mode (unused)

    Returns:
        Complete host shell script
    """
    host_script_parts = [
        f"CONTAINER_NAME={shlex.quote(container_name)}",
        f"TMP_SYSTEM={shlex.quote(tmp_paths.get('system', ''))}",
        f"TMP_SETTINGS={shlex.quote(tmp_paths.get('settings', ''))}",
        f"TMP_ENV={shlex.quote(tmp_paths.get('environment', ''))}",
        f"TMP_HELPME={shlex.quote(tmp_paths.get('helpme', ''))}",
        'cleanup() { '
        + 'if [ -n "$TMP_SYSTEM" ]; then rm -f -- "$TMP_SYSTEM" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_SETTINGS" ]; then rm -f -- "$TMP_SETTINGS" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_ENV" ]; then rm -f -- "$TMP_ENV" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_HELPME" ]; then rm -f -- "$TMP_HELPME" >/dev/null 2>&1 || true; fi; }',
        'finish() { cleanup; }',
        "trap finish EXIT",
    ]

    if rosetta_snippet:
        host_script_parts.append(rosetta_snippet)
    if gh_clone_snippet:
        host_script_parts.append(gh_clone_snippet)

    if attach_mode:
        # Attach to existing detached container (app already launched it)
        attach_cmd = f"docker attach {shlex.quote(container_name)}"
        host_script_parts.append(
            f'{attach_cmd}; STATUS=$?; if [ $STATUS -ne 0 ]; then {shell_log_statement("host", "docker", "ERROR", "container attach failed (exit $STATUS)")}; fi; if [ $STATUS -ne 0 ]; then read -r -p "Press Enter to close..."; fi; exit $STATUS'
        )
    
    return " ; ".join(host_script_parts)


def _cleanup_temp_files(tmp_paths: dict[str, str]) -> None:
    """Clean up temporary preflight script files.

    Args:
        tmp_paths: Dict mapping label to temp file path
    """
    for tmp in tmp_paths.values():
        try:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            # Best-effort cleanup: ignore errors while removing temporary files.
            pass


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
