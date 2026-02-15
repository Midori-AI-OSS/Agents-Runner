from __future__ import annotations

import importlib
import logging
from pathlib import Path

from agents_runner.agent_systems.models import AgentSystemPlugin


logger = logging.getLogger(__name__)

_DEFAULT_AGENT_SYSTEM = "codex"

_registry: dict[str, AgentSystemPlugin] | None = None


def available_agent_system_names() -> list[str]:
    """Return discovered agent system plugin names."""
    return sorted(_ensure_registry().keys())


def get_default_agent_system_name() -> str:
    """Return the default agent system name used for unknown inputs."""
    return _DEFAULT_AGENT_SYSTEM


def normalize_agent_system_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw and raw in _ensure_registry():
        return raw
    return _DEFAULT_AGENT_SYSTEM


def register_agent_system(plugin: AgentSystemPlugin) -> None:
    """Register an agent system plugin."""
    registry = _ensure_registry()
    name = str(getattr(plugin, "name", "") or "").strip().lower()
    if not name:
        raise ValueError("agent system plugin has no name")
    if name in registry:
        raise ValueError(f"duplicate agent system plugin name: {name}")
    registry[name] = plugin


def get_agent_system(name: str) -> AgentSystemPlugin:
    """Get a discovered agent system plugin by name."""
    key = str(name or "").strip().lower()
    registry = _ensure_registry()
    if key in registry:
        return registry[key]
    raise KeyError(f"unknown agent system: {name}")


def _ensure_registry() -> dict[str, AgentSystemPlugin]:
    global _registry
    if _registry is None:
        _registry = {}
        _discover_builtin_plugins(_registry)
    return _registry


def _discover_builtin_plugins(registry: dict[str, AgentSystemPlugin]) -> None:
    root = Path(__file__).resolve().parent
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if entry.name.startswith("__"):
            continue
        plugin_path = entry / "plugin.py"
        if not plugin_path.is_file():
            continue

        module_name = f"{__package__}.{entry.name}.plugin"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logger.warning(
                "agent system plugin import failed: %s (%s)", module_name, exc
            )
            continue

        plugin = getattr(module, "PLUGIN", None)
        if plugin is None:
            logger.warning("agent system plugin missing PLUGIN export: %s", module_name)
            continue

        name = str(getattr(plugin, "name", "") or "").strip().lower()
        if not name:
            logger.warning("agent system plugin has invalid name: %s", module_name)
            continue
        if name in registry:
            logger.warning(
                "duplicate agent system plugin name %r from %s", name, module_name
            )
            continue
        registry[name] = plugin
