from __future__ import annotations

from agents_runner.ide_systems.models import IdeAutoMountSpec
from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="visual-studio-code-bin",
    display_name="Visual Studio Code",
    package_name="visual-studio-code-bin",
    executable="code",
    launch_args=("--no-sandbox",),
    wait_process_pattern="comm=code|code-oss",
    auto_mount_specs=(
        IdeAutoMountSpec(
            host_path="~/.config/Code",
            container_path="/home/midori-ai/.config/Code",
            mode="rw",
        ),
        IdeAutoMountSpec(
            host_path="~/.vscode",
            container_path="/home/midori-ai/.vscode",
            mode="rw",
        ),
    ),
    auto_mount_host_keyring=True,
    auto_mount_session_dbus=True,
)
