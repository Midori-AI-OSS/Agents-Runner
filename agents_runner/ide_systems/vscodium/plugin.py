from __future__ import annotations

from agents_runner.ide_systems.models import IdeAutoMountSpec
from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="vscodium",
    display_name="VSCodium",
    package_name="vscodium-bin",
    executable="codium",
    launch_args=("--no-sandbox",),
    wait_process_pattern="comm=codium",
    auto_mount_specs=(
        IdeAutoMountSpec(
            host_path="~/.config/VSCodium",
            container_path="/home/midori-ai/.config/VSCodium",
            mode="rw",
        ),
        IdeAutoMountSpec(
            host_path="~/.vscode-oss",
            container_path="/home/midori-ai/.vscode-oss",
            mode="rw",
        ),
    ),
    auto_mount_host_keyring=True,
    auto_mount_session_dbus=True,
)
