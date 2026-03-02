from __future__ import annotations

from agents_runner.ide_systems.models import IdeAutoMountSpec
from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="visual-studio-code-bin",
    display_name="Visual Studio Code",
    package_name="visual-studio-code-bin",
    executable="code",
    launch_args=("--no-sandbox", "--wait"),
    auto_mount_specs=(
        IdeAutoMountSpec(
            host_path="~/.midoriai/agents-runner/ide/visual-studio-code-bin-config/.config/Code",
            container_path="/home/midori-ai/.config/Code",
            mode="rw",
        ),
        IdeAutoMountSpec(
            host_path="~/.midoriai/agents-runner/ide/visual-studio-code-bin-config/.vscode",
            container_path="/home/midori-ai/.vscode",
            mode="rw",
        ),
    ),
    auto_mount_host_keyring=False,
    auto_mount_session_dbus=False,
)
