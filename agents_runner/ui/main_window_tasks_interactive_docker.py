"""Docker launcher for interactive agent tasks.

This module handles Docker command construction, preflight script preparation,
and terminal script generation for launching interactive agent tasks.
"""

from __future__ import annotations

import os
import shlex
import socket
import tempfile
from datetime import datetime
from datetime import timezone
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import agent_requires_github_token
from agents_runner.agent_cli import available_agents
from agents_runner.agent_cli import verify_cli_clause
from agents_runner.docker_platform import ROSETTA_INSTALL_COMMAND
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.docker_platform import has_rosetta
from agents_runner.docker.image_builder import ensure_desktop_image
from agents_runner.docker.phase_image_builder import PREFLIGHTS_DIR
from agents_runner.docker.phase_image_builder import ensure_phase_image
from agents_runner.environments import Environment
from agents_runner.github_token import resolve_github_token
from agents_runner.log_format import format_log
from agents_runner.terminal_apps import launch_in_terminal
from agents_runner.core.shell_templates import git_identity_clause
from agents_runner.core.shell_templates import shell_log_statement
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _safe_str


def _publishes_container_port(spec: str, port: int) -> bool:
    base = str(spec or "").strip()
    if not base:
        return False
    base = base.split("/", 1)[0]
    container_part = base.rsplit(":", 1)[-1].strip()
    if not container_part:
        return False
    if container_part.isdigit():
        return int(container_part) == int(port)
    if "-" in container_part:
        left, right = (p.strip() for p in container_part.split("-", 1))
        if left.isdigit() and right.isdigit():
            start = int(left)
            end = int(right)
            p = int(port)
            return start <= p <= end
    return False


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
    skip_image_pull: bool = False,
    runtime_image_override: str | None = None,
    system_preflight_cached_override: bool | None = None,
    desktop_preflight_cached_override: bool | None = None,
    settings_preflight_cached_override: bool | None = None,
    environment_preflight_cached_override: bool | None = None,
    desktop_preflight_script_override: str | None = None,
) -> None:
    """Construct Docker command, generate host shell script, and launch terminal.

    Handles:
    - Preflight script preparation and mounting
    - Docker run command construction
    - Environment variables and port mapping
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
        skip_image_pull: If True, skip docker pull in host launcher script
        runtime_image_override: Optional precomputed runtime image
        system_preflight_cached_override: Optional precomputed system cache status
        desktop_preflight_cached_override: Optional precomputed desktop cache status
        settings_preflight_cached_override: Optional precomputed settings cache status
        environment_preflight_cached_override: Optional precomputed env cache status
        desktop_preflight_script_override: Optional precomputed desktop script
    """
    # Treat all interactive extra preflights as the desktop phase.
    desktop_preflight_script = str(extra_preflight_script or "")
    desktop_enabled = bool(
        "websockify" in desktop_preflight_script
        or "noVNC" in desktop_preflight_script
        or "[desktop]" in desktop_preflight_script
    )

    preflights_host_dir = PREFLIGHTS_DIR.resolve()
    system_preflight_path = preflights_host_dir / "pixelarch_yay.sh"
    system_preflight_script = ""
    if system_preflight_path.is_file():
        try:
            system_preflight_script = system_preflight_path.read_text(encoding="utf-8")
        except Exception:
            system_preflight_script = ""

    runtime_image = image
    system_preflight_cached = False
    desktop_preflight_cached = False
    settings_preflight_cached = False
    environment_preflight_cached = False
    container_caching_enabled = bool(
        env and getattr(env, "container_caching_enabled", False)
    )
    cache_system_enabled = bool(
        container_caching_enabled
        and env
        and getattr(env, "cache_system_preflight_enabled", False)
    )
    cache_settings_enabled = bool(
        container_caching_enabled
        and env
        and getattr(env, "cache_settings_preflight_enabled", False)
    )
    desktop_cache_enabled = bool(env and getattr(env, "cache_desktop_build", False))
    desktop_cache_enabled = desktop_cache_enabled and desktop_enabled

    use_precomputed_cache = all(
        value is not None
        for value in (
            runtime_image_override,
            system_preflight_cached_override,
            desktop_preflight_cached_override,
            settings_preflight_cached_override,
            environment_preflight_cached_override,
        )
    )

    def on_phase_log(line: str) -> None:
        main_window._on_task_log(task_id, line)

    if use_precomputed_cache:
        runtime_image = str(runtime_image_override or image)
        system_preflight_cached = bool(system_preflight_cached_override)
        desktop_preflight_cached = bool(desktop_preflight_cached_override)
        settings_preflight_cached = bool(settings_preflight_cached_override)
        environment_preflight_cached = bool(environment_preflight_cached_override)
        if desktop_preflight_script_override is not None:
            desktop_preflight_script = str(desktop_preflight_script_override or "")
    else:
        if cache_system_enabled and system_preflight_script.strip():
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
            desktop_base_image = runtime_image
            next_image = ensure_desktop_image(desktop_base_image, on_log=on_phase_log)
            desktop_preflight_cached = next_image != desktop_base_image
            runtime_image = next_image
            if desktop_preflight_cached:
                desktop_run_path = preflights_host_dir / "desktop_run.sh"
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

        if cache_settings_enabled and (settings_preflight_script or "").strip():
            next_image = ensure_phase_image(
                base_image=runtime_image,
                phase_name="settings",
                script_content=str(settings_preflight_script or ""),
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

    # Prepare preflight scripts and get mounts
    preflight_clause, preflight_mounts, tmp_paths = _prepare_preflight_scripts(
        task_token=task_token,
        desktop_preflight_script=desktop_preflight_script,
        settings_preflight_script=settings_preflight_script,
        environment_preflight_script=environment_preflight_script,
        skip_system=system_preflight_cached,
        skip_desktop=desktop_preflight_cached,
        skip_settings=settings_preflight_cached,
        skip_environment=environment_preflight_cached,
    )

    if preflight_clause is None:
        # Error during preflight preparation
        _handle_launch_error(
            main_window,
            task,
            tmp_paths,
            stain,
            spinner,
            "Failed to prepare preflight scripts",
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
            (cmd_parts and agent_requires_github_token(cmd_parts[0]))
            or (env and getattr(env, "gh_context_enabled", False))
        )
        if forward_gh_token:
            gh_token = resolve_github_token()
            if gh_token:
                env_args.extend(
                    ["-e", f"GH_TOKEN={gh_token}", "-e", f"GITHUB_TOKEN={gh_token}"]
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

        # Apply environment-specified ports (if any)
        for port_spec in (getattr(env, "ports", None) or []) if env else []:
            spec = str(port_spec or "").strip()
            if not spec:
                continue
            if desktop_enabled and _publishes_container_port(spec, 6080):
                continue
            port_args.extend(["-p", spec])

        # Prepare extra mounts
        extra_mount_args: list[str] = []

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
        if cmd_parts and cmd_parts[0] in set(available_agents()):
            verify_clause = verify_cli_clause(cmd_parts[0])

        container_script = (
            "set -euo pipefail; "
            f"{git_identity_clause()}{preflight_clause}{verify_clause}{target_cmd}"
        )

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
            docker_env_passthrough=[],
            image=runtime_image,
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

        # Build Rosetta warning snippet
        rosetta_snippet = ""
        if has_rosetta() is False:
            rosetta_snippet = shell_log_statement(
                "host",
                "docker",
                "WARN",
                f"Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}",
            )

        # Build docker pull command
        docker_pull_cmd = ":"
        if not skip_image_pull:
            docker_platform_args = docker_platform_args_for_pixelarch()
            docker_pull_parts = ["docker", "pull", *docker_platform_args, runtime_image]
            docker_pull_cmd = " ".join(shlex.quote(part) for part in docker_pull_parts)

        # Build host shell script
        host_script = _build_host_shell_script(
            container_name=container_name,
            task_token=task_token,
            tmp_paths=tmp_paths,
            finish_path=finish_path,
            gh_token_snippet="",
            rosetta_snippet=rosetta_snippet,
            docker_pull_cmd=docker_pull_cmd,
            docker_cmd=docker_cmd,
        )

        # Log base branch if specified
        if (desired_base or "").strip():
            main_window._on_task_log(
                task_id,
                format_log("gh", "branch", "INFO", f"base branch: {desired_base}"),
            )

        # Update settings
        main_window._settings_data["host_workdir"] = host_workdir
        main_window._settings_data[main_window._host_config_dir_key(agent_cli)] = (
            host_codex
        )
        main_window._settings_data["active_environment_id"] = env_id
        main_window._settings_data["interactive_terminal_id"] = str(
            getattr(terminal_opt, "terminal_id", "")
        )
        interactive_key = main_window._interactive_command_key(agent_cli)
        if not main_window._is_agent_help_interactive_launch(
            prompt=prompt, command=command
        ):
            main_window._settings_data[interactive_key] = (
                main_window._sanitize_interactive_command_value(
                    interactive_key, command
                )
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
            format_log(
                "ui",
                "launch",
                "INFO",
                f"launched in {_safe_str(getattr(terminal_opt, 'label', 'Terminal'))}",
            ),
        )

        # Launch terminal
        launch_in_terminal(terminal_opt, host_script, cwd=host_workdir)
        main_window._maybe_auto_navigate_on_task_start(interactive=True)
        main_window._new_task.reset_for_new_run()

    except Exception as exc:
        _handle_launch_error(main_window, task, tmp_paths, stain, spinner, str(exc))


def _prepare_preflight_scripts(
    task_token: str,
    desktop_preflight_script: str,
    settings_preflight_script: str | None,
    environment_preflight_script: str | None,
    *,
    skip_system: bool = False,
    skip_desktop: bool = False,
    skip_settings: bool = False,
    skip_environment: bool = False,
) -> tuple[str | None, list[str], dict[str, str]]:
    """Create temporary preflight script files and build mount args.

    Args:
        task_token: Unique task token for temp file naming
        desktop_preflight_script: Desktop phase script content
        settings_preflight_script: Global preflight script
        environment_preflight_script: Environment-specific preflight script
        skip_system: Skip runtime system phase because it was cached
        skip_desktop: Skip runtime desktop phase because it was cached
        skip_settings: Skip runtime settings phase because it was cached
        skip_environment: Skip runtime environment phase because it was cached

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
        "desktop": "",
        "settings": "",
        "environment": "",
    }

    desktop_container_path = f"/tmp/agents-runner-preflight-desktop-{task_token}.sh"
    settings_container_path = f"/tmp/agents-runner-preflight-settings-{task_token}.sh"
    environment_container_path = (
        f"/tmp/agents-runner-preflight-environment-{task_token}.sh"
    )

    preflights_host_dir = (
        Path(__file__).resolve().parent.parent / "preflights"
    ).resolve()
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

        preflights_scripts: dict[str, str] = {}
        try:
            for candidate in sorted(preflights_host_dir.glob("*.sh")):
                preflights_scripts[candidate.name] = candidate.read_text(
                    encoding="utf-8"
                ).strip()
        except Exception:
            preflights_scripts = {}

        preflight_clause += (
            f"PREFLIGHTS_DIR={shlex.quote(preflights_container_dir)}; "
            'export AGENTS_RUNNER_PREFLIGHTS_DIR="${PREFLIGHTS_DIR}"; '
        )

        if not skip_system:
            preflight_clause += (
                'PREFLIGHT_SYSTEM="${PREFLIGHTS_DIR}/pixelarch_yay.sh"; '
                f"{shell_log_statement('docker', 'preflight', 'INFO', 'system: starting')}; "
                '/bin/bash "${PREFLIGHT_SYSTEM}"; '
                f"{shell_log_statement('docker', 'preflight', 'INFO', 'system: done')}; "
            )

        def _append_optional_phase(
            *,
            label: str,
            script: str,
            container_path: str,
            tmp_key: str,
            skip: bool,
            env_var: str,
        ) -> None:
            nonlocal preflight_clause
            if skip:
                return
            stripped = str(script or "").strip()
            if not stripped:
                return
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
                    f'{env_var}="${{PREFLIGHTS_DIR}}/{matched}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', f'{label}: running')}; "
                    f'/bin/bash "${{{env_var}}}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', f'{label}: done')}; "
                )
                return

            tmp_paths[tmp_key] = _write_preflight_script(str(script or ""), label)
            preflight_mounts.extend(["-v", f"{tmp_paths[tmp_key]}:{container_path}:ro"])
            preflight_clause += (
                f"{env_var}={shlex.quote(container_path)}; "
                f"{shell_log_statement('docker', 'preflight', 'INFO', f'{label}: running')}; "
                f'/bin/bash "${{{env_var}}}"; '
                f"{shell_log_statement('docker', 'preflight', 'INFO', f'{label}: done')}; "
            )

        _append_optional_phase(
            label="desktop",
            script=desktop_preflight_script,
            container_path=desktop_container_path,
            tmp_key="desktop",
            skip=skip_desktop,
            env_var="PREFLIGHT_DESKTOP",
        )
        _append_optional_phase(
            label="settings",
            script=str(settings_preflight_script or ""),
            container_path=settings_container_path,
            tmp_key="settings",
            skip=skip_settings,
            env_var="PREFLIGHT_SETTINGS",
        )
        _append_optional_phase(
            label="environment",
            script=str(environment_preflight_script or ""),
            container_path=environment_container_path,
            tmp_key="environment",
            skip=skip_environment,
            env_var="PREFLIGHT_ENV",
        )

        return preflight_clause, preflight_mounts, tmp_paths

    except Exception:
        # Clean up any created temp files
        _cleanup_temp_files(tmp_paths)
        return None, [], tmp_paths


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

    Returns:
        Complete Docker command string
    """
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


def _build_host_shell_script(
    container_name: str,
    task_token: str,
    tmp_paths: dict[str, str],
    finish_path: str,
    gh_token_snippet: str,
    rosetta_snippet: str,
    docker_pull_cmd: str,
    docker_cmd: str,
) -> str:
    """Build host-side shell script with cleanup and error handling.

    Args:
        container_name: Container name
        task_token: Unique task token
        tmp_paths: Dict of temp file paths for cleanup
        finish_path: Path to finish file
        gh_token_snippet: GH token setup snippet
        rosetta_snippet: Rosetta warning snippet
        docker_pull_cmd: Docker pull command
        docker_cmd: Docker run command

    Returns:
        Complete host shell script
    """
    host_script_parts = [
        f"CONTAINER_NAME={shlex.quote(container_name)}",
        f"TMP_SYSTEM={shlex.quote(tmp_paths.get('system', ''))}",
        f"TMP_DESKTOP={shlex.quote(tmp_paths.get('desktop', ''))}",
        f"TMP_SETTINGS={shlex.quote(tmp_paths.get('settings', ''))}",
        f"TMP_ENV={shlex.quote(tmp_paths.get('environment', ''))}",
        f"FINISH_FILE={shlex.quote(finish_path)}",
        'write_finish() { STATUS="${1:-0}"; printf "%s\\n" "$STATUS" >"$FINISH_FILE" 2>/dev/null || true; }',
        'cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; '
        + 'if [ -n "$TMP_SYSTEM" ]; then rm -f -- "$TMP_SYSTEM" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_DESKTOP" ]; then rm -f -- "$TMP_DESKTOP" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_SETTINGS" ]; then rm -f -- "$TMP_SETTINGS" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_ENV" ]; then rm -f -- "$TMP_ENV" >/dev/null 2>&1 || true; fi; '
        + "} ",
        'finish() { STATUS=$?; if [ ! -e "$FINISH_FILE" ]; then write_finish "$STATUS"; fi; cleanup; }',
        "trap finish EXIT",
    ]

    if rosetta_snippet:
        host_script_parts.append(rosetta_snippet)

    host_script_parts.extend(
        [
            f'{docker_pull_cmd} || {{ STATUS=$?; {shell_log_statement("host", "docker", "ERROR", "docker pull failed (exit $STATUS)")}; write_finish "$STATUS"; read -r -p "Press Enter to close..."; exit $STATUS; }}',
            f'{docker_cmd}; STATUS=$?; if [ $STATUS -ne 0 ]; then {shell_log_statement("host", "docker", "ERROR", "container command failed (exit $STATUS)")}; fi; write_finish "$STATUS"; if [ $STATUS -ne 0 ]; then read -r -p "Press Enter to close..."; fi; exit $STATUS',
        ]
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
