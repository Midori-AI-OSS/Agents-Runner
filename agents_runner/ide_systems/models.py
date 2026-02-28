from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Protocol
from typing import runtime_checkable

IDE_DISPLAY_HOST_DESKTOP = "host_desktop"
IDE_DISPLAY_CONTAINER_DESKTOP = "container_desktop"
IDE_AUTO_MOUNTS_INHERIT = "inherit"
IDE_AUTO_MOUNTS_ENABLED = "enabled"
IDE_AUTO_MOUNTS_DISABLED = "disabled"

_ALLOWED_DISPLAY_TARGETS = {
    IDE_DISPLAY_HOST_DESKTOP,
    IDE_DISPLAY_CONTAINER_DESKTOP,
}
_ALLOWED_AUTO_MOUNTS_OVERRIDES = {
    IDE_AUTO_MOUNTS_INHERIT,
    IDE_AUTO_MOUNTS_ENABLED,
    IDE_AUTO_MOUNTS_DISABLED,
}


@dataclass(frozen=True)
class IdeAutoMountSpec:
    host_path: str
    container_path: str
    mode: str = "rw"


@dataclass(frozen=True)
class IdeSystemSpec:
    name: str
    display_name: str
    package_name: str
    executable: str
    launch_args: tuple[str, ...] = ()
    wait_process_pattern: str = ""
    auto_mount_specs: tuple[IdeAutoMountSpec, ...] = ()
    auto_mount_host_keyring: bool = False
    auto_mount_session_dbus: bool = False

    def build_launch_argv(self, *, workspace_dir: str) -> list[str]:
        workspace = str(workspace_dir or "").strip() or "/home/midori-ai/workspace"
        argv: list[str] = [str(self.executable or "").strip()]
        argv.extend(str(arg or "").strip() for arg in self.launch_args)
        argv.append(workspace)
        return [part for part in argv if part]

    def build_launch_command(self, *, workspace_dir: str) -> str:
        return " ".join(
            shlex.quote(part)
            for part in self.build_launch_argv(workspace_dir=workspace_dir)
        )


@runtime_checkable
class IdeSystemPlugin(Protocol):
    name: str
    display_name: str
    package_name: str
    wait_process_pattern: str
    auto_mount_specs: tuple[IdeAutoMountSpec, ...]
    auto_mount_host_keyring: bool
    auto_mount_session_dbus: bool

    def build_launch_command(self, *, workspace_dir: str) -> str: ...
    def build_launch_argv(self, *, workspace_dir: str) -> list[str]: ...


def normalize_ide_display_target(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in _ALLOWED_DISPLAY_TARGETS:
        return raw
    return IDE_DISPLAY_CONTAINER_DESKTOP


def normalize_ide_auto_mounts_override(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in _ALLOWED_AUTO_MOUNTS_OVERRIDES:
        return raw
    return IDE_AUTO_MOUNTS_INHERIT
