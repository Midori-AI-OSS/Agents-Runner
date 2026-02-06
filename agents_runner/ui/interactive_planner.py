"""Interactive task execution using unified planner/runner.

This module provides a bridge between the UI's interactive task launching
and the unified planner/runner flow. It handles:
- Building RunRequest from UI parameters
- Using planner to generate RunPlan
- Managing container lifecycle for interactive sessions
- Terminal attachment and cleanup
"""

from __future__ import annotations

import os
import shlex
import socket
import tempfile
from pathlib import Path

from agents_runner.agent_cli import verify_cli_clause
from agents_runner.agent_systems import requires_github_token
from agents_runner.core.shell_templates import git_identity_clause, shell_log_statement
from agents_runner.docker_platform import (
    ROSETTA_INSTALL_COMMAND,
    docker_platform_args_for_pixelarch,
    has_rosetta,
)
from agents_runner.github_token import resolve_github_token
from agents_runner.planner import (
    EnvironmentSpec,
    RunRequest,
    SubprocessDockerAdapter,
    plan_run,
)
from agents_runner.terminal_apps import launch_in_terminal
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class InteractiveLaunchConfig:
    """Configuration for launching an interactive task."""

    def __init__(
        self,
        agent_cli: str,
        prompt: str,
        command_parts: list[str],
        env_id: str,
        image: str,
        host_workdir: str,
        host_codex: str,
        container_workdir: str,
        container_agent_dir: str,
        container_name: str,
        task_token: str,
        agent_cli_args: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        extra_mounts: list[str] | None = None,
        settings_preflight_script: str | None = None,
        environment_preflight_script: str | None = None,
        extra_preflight_script: str = "",
        desktop_enabled: bool = False,
    ) -> None:
        """Initialize interactive launch configuration.

        Args:
            agent_cli: Agent CLI name (e.g., "codex", "claude")
            prompt: User prompt for the agent
            command_parts: Pre-built command parts from UI
            env_id: Environment ID
            image: Docker image to use
            host_workdir: Host workspace directory
            host_codex: Host config directory
            container_workdir: Container workspace path
            container_agent_dir: Container config path
            container_name: Container name to use
            task_token: Unique task token
            agent_cli_args: Additional agent CLI arguments
            env_vars: Environment variables to set
            extra_mounts: Additional mount strings (src:dst or src:dst:mode)
            settings_preflight_script: Global preflight script
            environment_preflight_script: Environment-specific preflight script
            extra_preflight_script: Additional preflight script (help mode, etc.)
            desktop_enabled: Whether desktop mode is enabled
        """
        self.agent_cli = agent_cli
        self.prompt = prompt
        self.command_parts = command_parts
        self.env_id = env_id
        self.image = image
        self.host_workdir = Path(host_workdir)
        self.host_codex = Path(host_codex)
        self.container_workdir = container_workdir
        self.container_agent_dir = container_agent_dir
        self.container_name = container_name
        self.task_token = task_token
        self.agent_cli_args = agent_cli_args or []
        self.env_vars = env_vars or {}
        self.extra_mounts = extra_mounts or []
        self.settings_preflight_script = settings_preflight_script
        self.environment_preflight_script = environment_preflight_script
        self.extra_preflight_script = extra_preflight_script
        self.desktop_enabled = desktop_enabled


def launch_interactive_task(
    config: InteractiveLaunchConfig,
    terminal_opt: object,
    finish_path: str,
    gh_clone_snippet: str = "",
) -> tuple[str | None, int | None]:
    """Launch interactive task using unified planner/runner flow.

    This function orchestrates the interactive task launch by:
    1. Building RunRequest from config
    2. Using planner to generate RunPlan
    3. Pulling image (before terminal opens)
    4. Building terminal script that:
       - Starts container with keepalive
       - Waits for ready
       - Attaches with docker exec -it
       - Handles cleanup
    5. Launching terminal

    Args:
        config: Interactive launch configuration
        terminal_opt: Terminal option object
        finish_path: Path to finish file for exit code tracking
        gh_clone_snippet: Optional git clone/update snippet

    Returns:
        Tuple of (container_name, host_port) where host_port is for desktop mode
        Note: Returns container_name (not ID) since container doesn't exist yet
    """
    # Prepare preflight scripts and mounts
    preflight_clause, preflight_mounts, tmp_paths = _prepare_preflight_scripts(
        config.task_token,
        config.settings_preflight_script,
        config.environment_preflight_script,
        config.extra_preflight_script,
    )

    if preflight_clause is None:
        logger.rprint("[interactive] Failed to prepare preflight scripts", mode="error")
        return None, None

    # Allocate port for desktop mode if enabled
    host_port = None
    if config.desktop_enabled:
        host_port = _allocate_desktop_port()

    try:
        # Build RunRequest
        request = _build_run_request(config, preflight_mounts, host_port)

        # Generate RunPlan
        plan = plan_run(request)

        # Override container name in plan (planner doesn't set it)
        from agents_runner.planner.models import DockerSpec, RunPlan

        docker_with_name = DockerSpec(
            image=plan.docker.image,
            container_name=config.container_name,
            workdir=plan.docker.workdir,
            mounts=plan.docker.mounts,
            env=plan.docker.env,
            keepalive_argv=plan.docker.keepalive_argv,
        )

        plan = RunPlan(
            interactive=plan.interactive,
            docker=docker_with_name,
            prompt_text=plan.prompt_text,
            exec_spec=plan.exec_spec,
            artifacts=plan.artifacts,
        )

        # Create adapter for pull phase only
        adapter = SubprocessDockerAdapter()

        # Phase 1: Pull image (before terminal opens)
        logger.rprint(f"[interactive] Pulling image: {config.image}", mode="normal")
        adapter.pull_image(plan.docker.image, timeout=60 * 15)

        # Phase 2: Build terminal script that will start container and attach
        docker_start_cmd = _build_docker_start_command(plan, host_port)
        docker_exec_cmd = _build_terminal_exec_command(
            container_name=config.container_name,
            command_parts=config.command_parts,
            preflight_clause=preflight_clause,
            agent_cli=config.agent_cli,
            container_workdir=config.container_workdir,
        )

        # Build host shell script
        host_script = _build_host_shell_script(
            container_name=config.container_name,
            task_token=config.task_token,
            tmp_paths=tmp_paths,
            finish_path=finish_path,
            gh_clone_snippet=gh_clone_snippet,
            docker_start_cmd=docker_start_cmd,
            docker_exec_cmd=docker_exec_cmd,
        )

        # Launch terminal
        logger.rprint("[interactive] Launching terminal", mode="normal")
        launch_in_terminal(terminal_opt, host_script, cwd=str(config.host_workdir))

        return config.container_name, host_port

    except Exception as exc:
        logger.rprint(f"[interactive] Launch failed: {exc!r}", mode="error")
        _cleanup_temp_files(tmp_paths)
        return None, None


def _build_run_request(
    config: InteractiveLaunchConfig,
    preflight_mounts: list[str],
    host_port: int | None,
) -> RunRequest:
    """Build RunRequest from interactive launch config.

    Args:
        config: Interactive launch configuration
        preflight_mounts: Preflight mount arguments
        host_port: Desktop port if desktop mode enabled

    Returns:
        RunRequest for planner
    """
    # Build environment variables
    env_vars = dict(config.env_vars)

    # Add GitHub token if needed
    if requires_github_token(config.agent_cli):
        gh_token = resolve_github_token()
        if gh_token:
            env_vars["GH_TOKEN"] = gh_token
            env_vars["GITHUB_TOKEN"] = gh_token

    # Add desktop env vars if enabled
    if config.desktop_enabled:
        env_vars["AGENTS_RUNNER_TASK_ID"] = config.task_token
        env_vars["DISPLAY"] = ":1"

    # Build extra mounts list
    extra_mounts = list(config.extra_mounts)

    # Add preflight mounts (convert from -v flag format)
    i = 0
    while i < len(preflight_mounts):
        if preflight_mounts[i] == "-v" and i + 1 < len(preflight_mounts):
            extra_mounts.append(preflight_mounts[i + 1])
            i += 2
        else:
            i += 1

    # Build EnvironmentSpec
    env_spec = EnvironmentSpec(
        env_id=config.env_id,
        image=config.image,
        env_vars=env_vars,
        extra_mounts=extra_mounts,
    )

    # Build RunRequest
    return RunRequest(
        interactive=True,
        system_name=config.agent_cli,
        prompt=config.prompt,
        environment=env_spec,
        host_workdir=config.host_workdir,
        host_config_dir=config.host_codex,
        extra_cli_args=config.agent_cli_args,
    )


def _build_docker_start_command(plan, host_port: int | None = None) -> str:
    """Build docker run command to start container with keepalive.

    Args:
        plan: RunPlan from planner
        host_port: Optional host port for desktop mode port mapping

    Returns:
        Complete docker run command string
    """
    docker = plan.docker
    docker_platform_args = docker_platform_args_for_pixelarch()

    cmd = ["docker", "run", "-d", *docker_platform_args]

    # Add container name if specified
    if docker.container_name:
        cmd.extend(["--name", docker.container_name])

    # Add working directory
    cmd.extend(["-w", str(docker.workdir)])

    # Add port mapping for desktop mode if specified
    if host_port is not None:
        cmd.extend(["-p", f"127.0.0.1:{host_port}:6080"])

    # Add environment variables
    for key, value in docker.env.items():
        cmd.extend(["-e", f"{key}={value}"])

    # Add volume mounts
    for mount in docker.mounts:
        mount_str = f"{mount.src}:{mount.dst}"
        if mount.mode == "ro":
            mount_str += ":ro"
        cmd.extend(["-v", mount_str])

    # Add image
    cmd.append(docker.image)

    # Add keepalive command
    cmd.extend(docker.keepalive_argv)

    return " ".join(shlex.quote(part) for part in cmd)


def _build_terminal_exec_command(
    container_name: str,
    command_parts: list[str],
    preflight_clause: str,
    agent_cli: str,
    container_workdir: str,
) -> str:
    """Build docker exec command for terminal attachment.

    Args:
        container_name: Container name to attach to
        command_parts: Pre-built command parts from UI
        preflight_clause: Preflight script clause
        agent_cli: Agent CLI name
        container_workdir: Container working directory

    Returns:
        Complete docker exec command string
    """
    # Build agent command from parts
    agent_cmd = " ".join(shlex.quote(part) for part in command_parts)

    # Build bash script with preflight and verification
    verify_clause = (
        verify_cli_clause(agent_cli)
        if agent_cli
        in {
            "codex",
            "claude",
            "copilot",
            "gemini",
        }
        else ""
    )

    bash_script = (
        "set -euo pipefail; "
        f"{git_identity_clause()}"
        f"{preflight_clause}"
        f"{verify_clause}"
        f"{agent_cmd}"
    )

    # Build docker exec command
    docker_exec_args = [
        "docker",
        "exec",
        "-it",
        "-w",
        container_workdir,
        container_name,
        "/bin/bash",
        "-lc",
        bash_script,
    ]

    return " ".join(shlex.quote(part) for part in docker_exec_args)


def _allocate_desktop_port() -> int:
    """Allocate a free port for desktop mode.

    Returns:
        Free port number
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


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
    environment_container_path = (
        f"/tmp/agents-runner-preflight-environment-{task_token}.sh"
    )
    extra_container_path = f"/tmp/agents-runner-preflight-extra-{task_token}.sh"

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
                # Cleanup attempt failed, but we're already handling an exception
                logger.rprint(
                    f"[interactive] Failed to close temp file descriptor {fd}",
                    mode="debug",
                )
            raise
        return tmp_path

    try:
        if not preflights_host_dir.is_dir():
            raise RuntimeError(f"Missing preflights directory: {preflights_host_dir}")
        system_preflight_path = preflights_host_dir / "pixelarch_yay.sh"
        if not system_preflight_path.is_file():
            raise RuntimeError(f"Missing system preflight: {system_preflight_path}")

        # Mount the entire preflights directory (read-only)
        preflight_mounts.extend(
            ["-v", f"{preflights_host_dir}:{preflights_container_dir}:ro"]
        )

        preflight_clause += (
            f"PREFLIGHTS_DIR={shlex.quote(preflights_container_dir)}; "
            'export AGENTS_RUNNER_PREFLIGHTS_DIR="${PREFLIGHTS_DIR}"; '
            'PREFLIGHT_SYSTEM="${PREFLIGHTS_DIR}/pixelarch_yay.sh"; '
            f"{shell_log_statement('docker', 'preflight', 'INFO', 'system: starting')}; "
            '/bin/bash "${PREFLIGHT_SYSTEM}"; '
            f"{shell_log_statement('docker', 'preflight', 'INFO', 'system: done')}; "
        )

        # Settings preflight (optional)
        if (settings_preflight_script or "").strip():
            preflights_scripts: dict[str, str] = {}
            try:
                for candidate in sorted(preflights_host_dir.glob("*.sh")):
                    preflights_scripts[candidate.name] = candidate.read_text(
                        encoding="utf-8"
                    ).strip()
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
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'settings: running')}; "
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'settings: done')}; "
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
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'settings: running')}; "
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'settings: done')}; "
                )

        # Environment preflight (optional)
        if (environment_preflight_script or "").strip():
            preflights_scripts_env: dict[str, str] = {}
            try:
                for candidate in sorted(preflights_host_dir.glob("*.sh")):
                    preflights_scripts_env[candidate.name] = candidate.read_text(
                        encoding="utf-8"
                    ).strip()
            except Exception:
                preflights_scripts_env = {}

            stripped_env = str(environment_preflight_script or "").strip()
            matched_env = next(
                (
                    name
                    for name, content in preflights_scripts_env.items()
                    if content == stripped_env and name != "pixelarch_yay.sh"
                ),
                None,
            )
            if matched_env:
                preflight_clause += (
                    f'PREFLIGHT_ENV="${{PREFLIGHTS_DIR}}/{matched_env}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'environment: running')}; "
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'environment: done')}; "
                )
            else:
                tmp_paths["environment"] = _write_preflight_script(
                    str(environment_preflight_script or ""), "environment"
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{tmp_paths['environment']}:{environment_container_path}:ro",
                    ]
                )
                preflight_clause += (
                    f"PREFLIGHT_ENV={shlex.quote(environment_container_path)}; "
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'environment: running')}; "
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'environment: done')}; "
                )

        # Extra preflight (optional)
        if (extra_preflight_script or "").strip():
            preflights_scripts_extra: dict[str, str] = {}
            try:
                for candidate in sorted(preflights_host_dir.glob("*.sh")):
                    preflights_scripts_extra[candidate.name] = candidate.read_text(
                        encoding="utf-8"
                    ).strip()
            except Exception:
                preflights_scripts_extra = {}

            stripped_extra = str(extra_preflight_script or "").strip()
            matched_extra = next(
                (
                    name
                    for name, content in preflights_scripts_extra.items()
                    if content == stripped_extra and name != "pixelarch_yay.sh"
                ),
                None,
            )
            if matched_extra:
                preflight_clause += (
                    f'PREFLIGHT_EXTRA="${{PREFLIGHTS_DIR}}/{matched_extra}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'extra: running')}; "
                    '/bin/bash "${PREFLIGHT_EXTRA}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'extra: done')}; "
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
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'extra: running')}; "
                    '/bin/bash "${PREFLIGHT_EXTRA}"; '
                    f"{shell_log_statement('docker', 'preflight', 'INFO', 'extra: done')}; "
                )

        return preflight_clause, preflight_mounts, tmp_paths

    except Exception:
        # Clean up any created temp files
        _cleanup_temp_files(tmp_paths)
        return None, [], tmp_paths


def _cleanup_temp_files(tmp_paths: dict[str, str]) -> None:
    """Clean up temporary preflight script files.

    Args:
        tmp_paths: Dict of temp file paths to clean up
    """
    for path in tmp_paths.values():
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except Exception as e:
                logger.rprint(
                    f"[interactive] Failed to remove temp file {path}: {e}", mode="debug"
                )


def _build_host_shell_script(
    container_name: str,
    task_token: str,
    tmp_paths: dict[str, str],
    finish_path: str,
    gh_clone_snippet: str,
    docker_start_cmd: str,
    docker_exec_cmd: str,
) -> str:
    """Build host-side shell script with cleanup and error handling.

    Args:
        container_name: Container name
        task_token: Unique task token
        tmp_paths: Dict of temp file paths for cleanup
        finish_path: Path to finish file
        gh_clone_snippet: Git clone/update snippet
        docker_start_cmd: Docker run command to start container
        docker_exec_cmd: Docker exec command to attach

    Returns:
        Complete host shell script
    """
    # Build Rosetta warning snippet
    rosetta_snippet = ""
    if has_rosetta() is False:
        rosetta_snippet = shell_log_statement(
            "host",
            "docker",
            "WARN",
            f"Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}",
        )

    host_script_parts = [
        f"CONTAINER_NAME={shlex.quote(container_name)}",
        f"TMP_SYSTEM={shlex.quote(tmp_paths.get('system', ''))}",
        f"TMP_SETTINGS={shlex.quote(tmp_paths.get('settings', ''))}",
        f"TMP_ENV={shlex.quote(tmp_paths.get('environment', ''))}",
        f"TMP_HELPME={shlex.quote(tmp_paths.get('helpme', ''))}",
        f"FINISH_FILE={shlex.quote(finish_path)}",
        'write_finish() { STATUS="${1:-0}"; printf "%s\\n" "$STATUS" >"$FINISH_FILE" 2>/dev/null || true; }',
        'cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; '
        + 'if [ -n "$TMP_SYSTEM" ]; then rm -f -- "$TMP_SYSTEM" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_SETTINGS" ]; then rm -f -- "$TMP_SETTINGS" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_ENV" ]; then rm -f -- "$TMP_ENV" >/dev/null 2>&1 || true; fi; '
        + 'if [ -n "$TMP_HELPME" ]; then rm -f -- "$TMP_HELPME" >/dev/null 2>&1 || true; fi; }',
        'finish() { STATUS=$?; if [ ! -e "$FINISH_FILE" ]; then write_finish "$STATUS"; fi; cleanup; }',
        "trap finish EXIT",
    ]

    if rosetta_snippet:
        host_script_parts.append(rosetta_snippet)

    if gh_clone_snippet:
        host_script_parts.append(gh_clone_snippet)

    # Start container with keepalive
    host_script_parts.append(f"{docker_start_cmd} || {{ write_finish 1; exit 1; }}")

    # Wait for container to be ready (simple poll loop)
    wait_ready_script = (
        "for i in $(seq 1 60); do "
        'STATE=$(docker inspect --format "{{.State.Status}}" "$CONTAINER_NAME" 2>/dev/null || echo "missing"); '
        'if [ "$STATE" = "running" ]; then break; fi; '
        'if [ "$STATE" = "exited" ] || [ "$STATE" = "dead" ] || [ "$STATE" = "missing" ]; then '
        "write_finish 1; exit 1; fi; "
        "sleep 0.5; "
        "done; "
        'if [ "$STATE" != "running" ]; then write_finish 1; exit 1; fi'
    )
    host_script_parts.append(wait_ready_script)

    # Execute command in container
    host_script_parts.append(docker_exec_cmd)

    return "\n".join(host_script_parts)
