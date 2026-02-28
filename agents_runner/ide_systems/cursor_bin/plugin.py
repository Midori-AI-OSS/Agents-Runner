from __future__ import annotations

from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="cursor-bin",
    display_name="Cursor",
    package_name="cursor-bin",
    executable="cursor",
    launch_args=("--no-sandbox",),
    wait_process_pattern="comm=electron;argv_contains=/usr/share/cursor/resources/app",
)
