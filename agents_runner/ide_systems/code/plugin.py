from __future__ import annotations

from agents_runner.ide_systems.models import IdeAutoMountSpec
from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="code",
    display_name="Code OSS",
    package_name="code",
    executable="code",
    launch_args=("--no-sandbox", "--wait"),
    auto_mount_specs=(
        IdeAutoMountSpec(
            host_path="~/.midoriai/agents-runner/ide/code-config/.config/Code - OSS",
            container_path="/home/midori-ai/.config/Code - OSS",
            mode="rw",
        ),
        IdeAutoMountSpec(
            host_path="~/.midoriai/agents-runner/ide/code-config/.vscode-oss",
            container_path="/home/midori-ai/.vscode-oss",
            mode="rw",
        ),
    ),
    auto_mount_host_keyring=False,
    auto_mount_session_dbus=False,
)
