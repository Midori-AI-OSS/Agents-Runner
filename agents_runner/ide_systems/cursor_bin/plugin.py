from __future__ import annotations

from agents_runner.ide_systems.models import IdeAutoMountSpec
from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="cursor-bin",
    display_name="Cursor",
    package_name="cursor-bin",
    executable="cursor",
    launch_args=("--no-sandbox",),
    wait_process_pattern="comm=electron;argv_contains=/usr/share/cursor/resources/app",
    auto_mount_specs=(
        IdeAutoMountSpec(
            host_path="~/.config/Cursor",
            container_path="/home/midori-ai/.config/Cursor",
            mode="rw",
        ),
        IdeAutoMountSpec(
            host_path="~/.cursor",
            container_path="/home/midori-ai/.cursor",
            mode="rw",
        ),
    ),
    auto_mount_host_keyring=True,
    auto_mount_session_dbus=True,
)
