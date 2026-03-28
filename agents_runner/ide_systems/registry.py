from __future__ import annotations

import importlib
import logging
from pathlib import Path

from agents_runner.ide_systems.models import IdeSystemPlugin

logger = logging.getLogger(__name__)

_DEFAULT_IDE_SYSTEM = "visual-studio-code-bin"

_registry: dict[str, IdeSystemPlugin] | None = None


def available_ide_system_names() -> list[str]:
    return sorted(_ensure_registry().keys())


def get_default_ide_system_name() -> str:
    return _DEFAULT_IDE_SYSTEM


def normalize_ide_system_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw and raw in _ensure_registry():
        return raw
    return _DEFAULT_IDE_SYSTEM


def register_ide_system(plugin: IdeSystemPlugin) -> None:
    registry = _ensure_registry()
    name = str(getattr(plugin, "name", "") or "").strip().lower()
    if not name:
        raise ValueError("ide system plugin has no name")
    if name in registry:
        raise ValueError(f"duplicate ide system plugin name: {name}")
    registry[name] = plugin


def get_ide_system(name: str) -> IdeSystemPlugin:
    key = str(name or "").strip().lower()
    registry = _ensure_registry()
    if key in registry:
        return registry[key]
    raise KeyError(f"unknown ide system: {name}")


def _ensure_registry() -> dict[str, IdeSystemPlugin]:
    global _registry
    if _registry is None:
        _registry = {}
        _discover_builtin_plugins(_registry)
    return _registry


def _discover_builtin_plugins(registry: dict[str, IdeSystemPlugin]) -> None:
    root = Path(__file__).resolve().parent
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith("__"):
            continue
        plugin_path = entry / "plugin.py"
        if not plugin_path.is_file():
            continue

        module_name = f"{__package__}.{entry.name}.plugin"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logger.warning("ide system plugin import failed: %s (%s)", module_name, exc)
            continue

        plugin = getattr(module, "PLUGIN", None)
        if plugin is None:
            logger.warning("ide system plugin missing PLUGIN export: %s", module_name)
            continue

        name = str(getattr(plugin, "name", "") or "").strip().lower()
        if not name:
            logger.warning("ide system plugin has invalid name: %s", module_name)
            continue
        if name in registry:
            logger.warning(
                "duplicate ide system plugin name %r from %s", name, module_name
            )
            continue
        registry[name] = plugin
