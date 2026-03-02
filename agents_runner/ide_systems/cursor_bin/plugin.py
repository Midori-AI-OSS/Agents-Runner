from __future__ import annotations

from agents_runner.ide_systems.models import IdeAutoMountSpec
from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="cursor-bin",
    display_name="Cursor",
    package_name="cursor-bin",
    executable="cursor",
    launch_args=("--no-sandbox", "--wait"),
    auto_mount_specs=(
        IdeAutoMountSpec(
            host_path="~/.midoriai/agents-runner/ide/cursor-bin-config/.config/Cursor",
            container_path="/home/midori-ai/.config/Cursor",
            mode="rw",
        ),
        IdeAutoMountSpec(
            host_path="~/.midoriai/agents-runner/ide/cursor-bin-config/.cursor",
            container_path="/home/midori-ai/.cursor",
            mode="rw",
        ),
    ),
    auto_mount_host_keyring=False,
    auto_mount_session_dbus=False,
)
