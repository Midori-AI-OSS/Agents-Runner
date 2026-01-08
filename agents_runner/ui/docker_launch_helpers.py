"""Helper functions for Docker terminal task launching.

This module contains helper functions for building Docker commands,
preparing preflight scripts, and generating host shell scripts.
"""

from __future__ import annotations

import os
import shlex
import tempfile
from pathlib import Path

from agents_runner.docker_platform import docker_platform_args_for_pixelarch


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

    system_container_path = f"/tmp/codex-preflight-system-{task_token}.sh"
    settings_container_path = f"/tmp/codex-preflight-settings-{task_token}.sh"
    environment_container_path = f"/tmp/codex-preflight-environment-{task_token}.sh"
    helpme_container_path = f"/tmp/codex-preflight-helpme-{task_token}.sh"

    def _write_preflight_script(script: str, label: str) -> str:
        """Write a preflight script to a temporary file."""
        fd, tmp_path = tempfile.mkstemp(
            prefix=f"codex-preflight-{label}-{task_token}-", suffix=".sh"
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
                pass
            raise
        return tmp_path

    try:
        # System preflight (required)
        system_preflight_path = (
            Path(__file__).resolve().parent.parent
            / "preflights"
            / "pixelarch_yay.sh"
        )
        system_preflight_script = system_preflight_path.read_text(encoding="utf-8")
        if not system_preflight_script.strip():
            raise RuntimeError(f"Missing system preflight: {system_preflight_path}")

        tmp_paths["system"] = _write_preflight_script(system_preflight_script, "system")
        preflight_mounts.extend(
            ["-v", f"{tmp_paths['system']}:{system_container_path}:ro"]
        )
        preflight_clause += (
            f"PREFLIGHT_SYSTEM={shlex.quote(system_container_path)}; "
            'echo "[preflight] system: starting"; '
            '/bin/bash "${PREFLIGHT_SYSTEM}"; '
            'echo "[preflight] system: done"; '
        )

        # Settings preflight (optional)
        if (settings_preflight_script or "").strip():
            tmp_paths["settings"] = _write_preflight_script(
                str(settings_preflight_script or ""), "settings"
            )
            preflight_mounts.extend(
                ["-v", f"{tmp_paths['settings']}:{settings_container_path}:ro"]
            )
            preflight_clause += (
                f"PREFLIGHT_SETTINGS={shlex.quote(settings_container_path)}; "
                'echo "[preflight] settings: running"; '
                '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                'echo "[preflight] settings: done"; '
            )

        # Environment preflight (optional)
        if (environment_preflight_script or "").strip():
            tmp_paths["environment"] = _write_preflight_script(
                str(environment_preflight_script or ""), "environment"
            )
            preflight_mounts.extend(
                ["-v", f"{tmp_paths['environment']}:{environment_container_path}:ro"]
            )
            preflight_clause += (
                f"PREFLIGHT_ENV={shlex.quote(environment_container_path)}; "
                'echo "[preflight] environment: running"; '
                '/bin/bash "${PREFLIGHT_ENV}"; '
                'echo "[preflight] environment: done"; '
            )

        # Extra preflight (optional, help mode, etc.)
        if str(extra_preflight_script or "").strip():
            tmp_paths["helpme"] = _write_preflight_script(
                str(extra_preflight_script or ""), "helpme"
            )
            preflight_mounts.extend(
                ["-v", f"{tmp_paths['helpme']}:{helpme_container_path}:ro"]
            )
            preflight_clause += (
                f"PREFLIGHT_HELP={shlex.quote(helpme_container_path)}; "
                'echo "[preflight] helpme: running"; '
                '/bin/bash "${PREFLIGHT_HELP}"; '
                'echo "[preflight] helpme: done"; '
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
    gh_clone_snippet: str,
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
        gh_clone_snippet: Git clone/update snippet
        docker_pull_cmd: Docker pull command
        docker_cmd: Docker run command

    Returns:
        Complete host shell script
    """
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

    if gh_token_snippet:
        host_script_parts.append(gh_token_snippet)
    if rosetta_snippet:
        host_script_parts.append(rosetta_snippet)
    if gh_clone_snippet:
        host_script_parts.append(gh_clone_snippet)

    host_script_parts.extend(
        [
            f'{docker_pull_cmd} || {{ STATUS=$?; echo "[host] docker pull failed (exit $STATUS)"; write_finish "$STATUS"; read -r -p "Press Enter to close..."; exit $STATUS; }}',
            f'{docker_cmd}; STATUS=$?; if [ $STATUS -ne 0 ]; then echo "[host] container command failed (exit $STATUS)"; fi; write_finish "$STATUS"; if [ $STATUS -ne 0 ]; then read -r -p "Press Enter to close..."; fi; exit $STATUS',
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
            pass
