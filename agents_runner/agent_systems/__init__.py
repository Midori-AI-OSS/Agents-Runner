"""Agent system plugins.

This package provides a small plugin system for agent CLIs (codex, claude, copilot,
gemini, ...). Each agent system is implemented as a folder-based plugin under
`agents_runner/agent_systems/<name>/plugin.py`.
"""

from agents_runner.agent_systems.registry import (
    available_agent_system_names,
    get_agent_system,
    get_default_agent_system_name,
    normalize_agent_system_name,
    register_agent_system,
)

__all__ = [
    "available_agent_system_names",
    "get_agent_system",
    "get_default_agent_system_name",
    "normalize_agent_system_name",
    "register_agent_system",
]
