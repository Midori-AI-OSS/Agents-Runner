"""
Helpers for agent identity keys.

Cooldowns and attempt history must be tracked for the exact agent + configuration
used for an execution attempt.
"""

from __future__ import annotations

import os


def normalize_host_config_dir(path: str) -> str:
    path = os.path.expanduser(str(path or "").strip())
    if not path:
        return ""
    return os.path.abspath(path)


def cooldown_key(
    *,
    agent_cli: str,
    host_config_dir: str,
    agent_cli_args: list[str] | tuple[str, ...],
) -> str:
    agent_cli = str(agent_cli or "").strip().lower()
    host_config_dir = normalize_host_config_dir(host_config_dir)
    args = list(agent_cli_args or [])
    args_str = " ".join(str(a) for a in args if str(a))
    if host_config_dir or args_str:
        return f"{agent_cli}::{host_config_dir}::{args_str}"
    return agent_cli

