"""IDE system plugins.

This package provides folder-based IDE plugins used by Run IDE launches.
"""

from agents_runner.ide_systems.models import IDE_DISPLAY_CONTAINER_DESKTOP
from agents_runner.ide_systems.models import IDE_DISPLAY_HOST_DESKTOP
from agents_runner.ide_systems.models import IDE_AUTO_MOUNTS_DISABLED
from agents_runner.ide_systems.models import IDE_AUTO_MOUNTS_ENABLED
from agents_runner.ide_systems.models import IDE_AUTO_MOUNTS_INHERIT
from agents_runner.ide_systems.models import IdeAutoMountSpec
from agents_runner.ide_systems.models import normalize_ide_auto_mounts_override
from agents_runner.ide_systems.models import normalize_ide_display_target
from agents_runner.ide_systems.registry import available_ide_system_names
from agents_runner.ide_systems.registry import get_default_ide_system_name
from agents_runner.ide_systems.registry import get_ide_system
from agents_runner.ide_systems.registry import normalize_ide_system_name
from agents_runner.ide_systems.registry import register_ide_system

__all__ = [
    "IDE_DISPLAY_CONTAINER_DESKTOP",
    "IDE_DISPLAY_HOST_DESKTOP",
    "IDE_AUTO_MOUNTS_DISABLED",
    "IDE_AUTO_MOUNTS_ENABLED",
    "IDE_AUTO_MOUNTS_INHERIT",
    "IdeAutoMountSpec",
    "available_ide_system_names",
    "get_default_ide_system_name",
    "get_ide_system",
    "normalize_ide_auto_mounts_override",
    "normalize_ide_display_target",
    "normalize_ide_system_name",
    "register_ide_system",
]
