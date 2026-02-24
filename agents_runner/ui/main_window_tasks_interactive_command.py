"""Command builder for interactive agent tasks.

This module parses the user-provided command string and delegates agent-specific
argument/prompt handling to the selected agent-system plugin.
"""

from __future__ import annotations

import shlex

from agents_runner.agent_cli import build_interactive_cmd
from agents_runner.agent_systems import normalize_agent_system_name


def build_agent_command_parts(
    command: str,
    agent_cli: str,
    agent_cli_args: list[str],
    prompt: str,
    host_workdir: str,
    host_config_dir: str | None = None,
    is_help_launch: bool,
    help_repos_dir: str = "/home/midori-ai/.agent-help/repos",
) -> list[str]:
    """Build command parts with agent-system plugin handling."""
    agent_cli = normalize_agent_system_name(agent_cli)
    command = str(command or "").strip()
    extra_args = list(agent_cli_args or [])
    if command.startswith("-"):
        extra_args = shlex.split(command) + extra_args
        command = ""
    resolved_host_config_dir = str(host_config_dir or "").strip() or None
    return build_interactive_cmd(
        agent=agent_cli,
        prompt=str(prompt or ""),
        host_workdir=str(host_workdir or "."),
        host_config_dir=resolved_host_config_dir,
        agent_cli_args=extra_args,
        command=command,
        is_help_launch=bool(is_help_launch),
        help_repos_dir=str(help_repos_dir or ""),
    )
