"""Command builder for interactive agent tasks.

This module parses the user-provided command string and delegates agent-specific
argument/prompt handling to the selected agent-system plugin.
"""

from __future__ import annotations

import shlex

from agents_runner.agent_cli import available_agents
from agents_runner.agent_systems import get_agent_system


def build_agent_command_parts(
    command: str,
    agent_cli: str,
    agent_cli_args: list[str],
    prompt: str,
    is_help_launch: bool,
    help_repos_dir: str = "/home/midori-ai/.agent-help/repos",
) -> list[str]:
    """Build command parts with agent-system plugin handling."""
    agent_cli = str(agent_cli or "").strip().lower() or "codex"

    if command.startswith("-"):
        cmd_parts = [agent_cli, *shlex.split(command)]
    else:
        cmd_parts = shlex.split(command)

    if not cmd_parts:
        return ["bash"]

    head = str(cmd_parts[0] or "").strip().lower()
    known = set(available_agents())
    if head not in known:
        return cmd_parts

    cmd_parts[0] = head
    return get_agent_system(head).build_interactive_command_parts(
        cmd_parts=cmd_parts,
        agent_cli_args=list(agent_cli_args or []),
        prompt=str(prompt or ""),
        is_help_launch=bool(is_help_launch),
        help_repos_dir=str(help_repos_dir or ""),
    )
