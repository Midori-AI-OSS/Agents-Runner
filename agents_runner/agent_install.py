from __future__ import annotations

import shlex
import subprocess
import threading
import time

from dataclasses import dataclass

from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_agent_system


_DEBUG_AGENT_COMMANDS = {
    "echo",
    "sh",
    "bash",
    "true",
    "false",
    "/bin/sh",
    "/bin/bash",
    "/usr/bin/sh",
    "/usr/bin/bash",
}

_PROBE_CACHE_LOCK = threading.Lock()
_PROBE_CACHE: dict[tuple[str, str, tuple[str, ...], str], bool] = {}
_PROBE_IMAGE_IDENTITY_BY_REF: dict[str, str] = {}


@dataclass(frozen=True)
class AgentInstallPlan:
    agent_cli: str
    verify_executable: str
    install_command: str
    phase_name: str
    script_content: str


def _safe_phase_suffix(value: str) -> str:
    safe = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())
    return safe or "agent"


def _safe_probe_token(value: str, *, fallback: str) -> str:
    token = "".join(
        ch
        for ch in str(value or "").strip().lower()
        if ch.isalnum() or ch in {"-", "_"}
    )
    return token or fallback


def _resolve_image_identity(image: str) -> str:
    image_ref = str(image or "").strip()
    if not image_ref:
        return "unknown"
    try:
        completed = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                image_ref,
                "--format",
                "{{.Id}}",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=20.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return f"ref:{image_ref}"
    if completed.returncode != 0:
        return f"ref:{image_ref}"
    identity = str(completed.stdout or "").strip()
    if identity.startswith("sha256:"):
        identity = identity[7:]
    return identity or f"ref:{image_ref}"


def _build_probe_container_name(*, task_token: str, agent_cli: str) -> str:
    task = _safe_probe_token(task_token, fallback="task")
    cli = _safe_probe_token(agent_cli, fallback="agent")
    suffix = _safe_probe_token(str(time.time_ns()), fallback="0")
    name = f"agents-runner-probe-{task}-{cli}-{suffix}"
    return name[:63].rstrip("-")


def probe_agent_executable_in_image(
    *,
    image: str,
    agent_cli: str,
    platform_args: list[str] | tuple[str, ...] | None = None,
    task_token: str = "task",
    timeout_s: float = 45.0,
) -> bool:
    image_ref = str(image or "").strip()
    cli = str(agent_cli or "").strip().lower()
    if not image_ref or not cli:
        return False
    if cli in _DEBUG_AGENT_COMMANDS:
        return True

    normalized_platform = tuple(
        part for part in (str(part).strip() for part in (platform_args or [])) if part
    )
    image_identity = _resolve_image_identity(image_ref)
    cache_key = (image_ref, image_identity, normalized_platform, cli)

    with _PROBE_CACHE_LOCK:
        previous_identity = _PROBE_IMAGE_IDENTITY_BY_REF.get(image_ref)
        if previous_identity and previous_identity != image_identity:
            stale_keys = [
                key
                for key in _PROBE_CACHE.keys()
                if key[0] == image_ref and key[1] != image_identity
            ]
            for stale in stale_keys:
                _PROBE_CACHE.pop(stale, None)
        _PROBE_IMAGE_IDENTITY_BY_REF[image_ref] = image_identity
        cached = _PROBE_CACHE.get(cache_key)
        if cached is not None:
            return cached

    quoted_cli = shlex.quote(cli)
    probe_command = f"command -v {quoted_cli} >/dev/null 2>&1"
    container_name = _build_probe_container_name(task_token=task_token, agent_cli=cli)
    probe_args = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        *list(normalized_platform),
        image_ref,
        "/bin/bash",
        "-lc",
        probe_command,
    ]
    try:
        completed = subprocess.run(
            probe_args,
            capture_output=True,
            check=False,
            text=True,
            timeout=max(1.0, float(timeout_s)),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"agent probe timed out for {cli} in image {image_ref}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"agent probe failed to execute docker: {exc}") from exc

    if completed.returncode == 0:
        available = True
    elif completed.returncode == 1:
        available = False
    else:
        stderr = str(completed.stderr or "").strip()
        stdout = str(completed.stdout or "").strip()
        detail = stderr or stdout or f"docker run probe exited {completed.returncode}"
        raise RuntimeError(
            f"agent probe failed for {cli} in image {image_ref}: {detail}"
        )

    with _PROBE_CACHE_LOCK:
        _PROBE_CACHE[cache_key] = available
    return available


def build_agent_install_script(
    *,
    agent_cli: str,
    verify_executable: str,
    install_command: str,
) -> str:
    cli = str(agent_cli or "").strip().lower()
    verify = str(verify_executable or "").strip() or cli
    command = str(install_command or "").strip()
    if not cli or not verify or not command:
        return ""

    quoted_verify = shlex.quote(verify)
    escaped_cli = cli.replace("\\", "\\\\").replace('"', '\\"')
    escaped_command = command.replace("\\", "\\\\").replace('"', '\\"')
    escaped_verify = verify.replace("\\", "\\\\").replace('"', '\\"')

    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"if command -v {quoted_verify} >/dev/null 2>&1; then",
        f'  echo "[install/agent][INFO] {escaped_cli}: executable already available"',
        "  exit 0",
        "fi",
        "",
        (
            f'echo "[install/agent][INFO] {escaped_cli}: executable missing; '
            'running install command"'
        ),
        f'echo "[install/agent][INFO] {escaped_cli}: install command -> {escaped_command}"',
        command,
        "",
        f"if ! command -v {quoted_verify} >/dev/null 2>&1; then",
        (
            f'  echo "[install/agent][ERROR] {escaped_cli}: executable '
            f'{escaped_verify} still missing in PATH=$PATH" >&2'
        ),
        (
            f'  echo "[install/agent][ERROR] {escaped_cli}: run manually -> '
            f'{escaped_command}" >&2'
        ),
        "  exit 127",
        "fi",
        "",
        f'echo "[install/agent][INFO] {escaped_cli}: install complete"',
    ]
    return "\n".join(lines) + "\n"


def resolve_agent_install_plan(
    *,
    agent_cli: str,
    include_internal: bool = False,
) -> AgentInstallPlan | None:
    cli = str(agent_cli or "").strip().lower()
    if not cli or cli in _DEBUG_AGENT_COMMANDS:
        return None

    known = set(available_agent_system_names(include_internal=True))
    if cli not in known:
        return None

    plugin = get_agent_system(cli)
    if not include_internal and bool(getattr(plugin, "internal_only", False)):
        return None

    install_command = str(plugin.install_command() or "").strip()
    if not install_command:
        return None

    verify_executable = cli
    phase_name = f"install-agent-{_safe_phase_suffix(cli)}"
    script_content = build_agent_install_script(
        agent_cli=cli,
        verify_executable=verify_executable,
        install_command=install_command,
    )
    if not script_content.strip():
        return None

    return AgentInstallPlan(
        agent_cli=cli,
        verify_executable=verify_executable,
        install_command=install_command,
        phase_name=phase_name,
        script_content=script_content,
    )
