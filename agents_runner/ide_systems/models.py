from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

IDE_DISPLAY_HOST_DESKTOP = "host_desktop"
IDE_DISPLAY_CONTAINER_DESKTOP = "container_desktop"

_ALLOWED_DISPLAY_TARGETS = {
    IDE_DISPLAY_HOST_DESKTOP,
    IDE_DISPLAY_CONTAINER_DESKTOP,
}


@dataclass(frozen=True)
class IdeSystemSpec:
    name: str
    display_name: str
    package_name: str
    executable: str

    def build_launch_command(self, *, workspace_dir: str) -> str:
        workspace = str(workspace_dir or "").strip() or "/home/midori-ai/workspace"
        return f"{self.executable} {workspace}"


@runtime_checkable
class IdeSystemPlugin(Protocol):
    name: str
    display_name: str
    package_name: str

    def build_launch_command(self, *, workspace_dir: str) -> str: ...


def normalize_ide_display_target(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in _ALLOWED_DISPLAY_TARGETS:
        return raw
    return IDE_DISPLAY_CONTAINER_DESKTOP
