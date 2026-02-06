"""Plugin registry for agent systems.

Auto-discovers and registers plugins from agents_runner/agent_systems/*/plugin.py.
Provides safe plugin loading with error handling and validation.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents_runner.agent_systems.models import AgentSystemPlugin

logger = logging.getLogger(__name__)

# Global plugin registry
_plugins: dict[str, AgentSystemPlugin] = {}


def discover_plugins() -> None:
    """Auto-discover plugins from agents_runner/agent_systems/*/plugin.py.

    Safely loads plugins and registers them by name. Import failures are logged
    but do not crash the application.
    """
    agent_systems_dir = Path(__file__).parent
    plugin_dirs = [
        d for d in agent_systems_dir.iterdir() if d.is_dir() and d.name != "__pycache__"
    ]

    for plugin_dir in plugin_dirs:
        plugin_file = plugin_dir / "plugin.py"
        if not plugin_file.exists():
            continue

        plugin_module_name = f"agents_runner.agent_systems.{plugin_dir.name}.plugin"
        try:
            module = importlib.import_module(plugin_module_name)
            if not hasattr(module, "plugin"):
                logger.warning(
                    "Plugin module %s does not have a 'plugin' attribute, skipping",
                    plugin_module_name,
                )
                continue

            plugin = module.plugin
            if not hasattr(plugin, "name"):
                logger.warning(
                    "Plugin in %s does not have a 'name' attribute, skipping",
                    plugin_module_name,
                )
                continue

            # Validate unique name
            if plugin.name in _plugins:
                logger.error(
                    "Duplicate plugin name '%s' found in %s, skipping",
                    plugin.name,
                    plugin_module_name,
                )
                continue

            # Validate capabilities
            if not hasattr(plugin, "capabilities"):
                logger.warning(
                    "Plugin '%s' does not have capabilities, skipping",
                    plugin.name,
                )
                continue

            _plugins[plugin.name] = plugin
            logger.info("Registered agent system plugin: %s", plugin.name)

        except Exception as e:
            logger.error(
                "Failed to load plugin from %s: %s",
                plugin_module_name,
                e,
                exc_info=True,
            )


def register_plugin(plugin: AgentSystemPlugin) -> None:
    """Manually register a plugin.

    Args:
        plugin: The plugin to register.

    Raises:
        ValueError: If a plugin with the same name is already registered.
    """
    if plugin.name in _plugins:
        raise ValueError(f"Plugin with name '{plugin.name}' is already registered")
    _plugins[plugin.name] = plugin
    logger.info("Manually registered agent system plugin: %s", plugin.name)


def get_plugin(name: str) -> AgentSystemPlugin | None:
    """Get a plugin by name.

    Args:
        name: The name of the plugin to retrieve.

    Returns:
        The plugin if found, None otherwise.
    """
    return _plugins.get(name)


def list_plugins() -> list[str]:
    """List all registered plugin names.

    Returns:
        A list of plugin names.
    """
    return list(_plugins.keys())


def clear_plugins() -> None:
    """Clear all registered plugins.

    This is primarily useful for testing.
    """
    _plugins.clear()
