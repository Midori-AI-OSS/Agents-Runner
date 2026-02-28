from __future__ import annotations

from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="vscodium",
    display_name="VSCodium",
    package_name="vscodium-bin",
    executable="codium",
    launch_args=("--no-sandbox",),
    wait_process_pattern="codium",
)
