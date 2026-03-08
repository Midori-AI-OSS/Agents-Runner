from __future__ import annotations

import shlex

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
